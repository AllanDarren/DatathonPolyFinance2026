"""Deployment (role B only). Works on Windows, macOS and Linux; needs the AWS CLI v2 and Python 3.11+.

    python scripts/deploy.py deploy        # build zip, package, deploy stack, upload data   (make deploy)
    python scripts/deploy.py upload-data   # data/*.csv -> starter/, data/snapshots/*.json -> snapshots/
    python scripts/deploy.py deploy-web    # npm build with VITE_API_URL, sync to S3, invalidate CloudFront
    python scripts/deploy.py outputs       # print API and site URLs
    python scripts/deploy.py destroy       # empty buckets + delete stack, after typed confirmation

Credentials: from the environment or an AWS profile. For convenience, variables from
`.env` are loaded if present (existing variables win); nothing is ever printed.

Config (env): STACK_NAME (alphaforge), AWS_REGION (us-east-1), LLM_PROVIDER (bedrock),
BEDROCK_MODEL_ID (required for bedrock), BUDGET_EMAIL (optional, creates a cost alert).
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "infra" / "template.yaml"
PACKAGED = ROOT / "infra" / ".packaged.yaml"
OUTPUTS_FILE = ROOT / ".build" / "stack_outputs.json"


def load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cfg() -> dict[str, str]:
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    os.environ["AWS_REGION"] = os.environ["AWS_DEFAULT_REGION"] = region
    return {"stack": os.environ.get("STACK_NAME", "alphaforge"), "region": region}


def aws(*args: str, capture: bool = True) -> str:
    exe = shutil.which("aws")
    if not exe:
        raise SystemExit("AWS CLI v2 introuvable (https://aws.amazon.com/cli/).")
    res = subprocess.run([exe, *args], text=True, capture_output=capture)
    if res.returncode != 0:
        raise SystemExit(f"aws {' '.join(args[:2])} a échoué:\n{(res.stderr or '').strip()}")
    return res.stdout if capture else ""


def boto(service: str):
    import boto3

    return boto3.client(service, region_name=os.environ["AWS_REGION"])


def account_id() -> str:
    return boto("sts").get_caller_identity()["Account"]


def git_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True,
                             capture_output=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "dev"


def foundation_model_of(model_id: str) -> str:
    """us.anthropic.x / global.anthropic.x / eu.amazon.x -> anthropic.x (for the IAM resource)."""
    head, _, rest = model_id.partition(".")
    return rest if head in {"us", "eu", "apac", "global", "ca", "jp", "au"} and rest else model_id


def artifacts_bucket(region: str) -> str:
    name = f"alphaforge-artifacts-{account_id()}-{region}"
    s3 = boto("s3")
    try:
        s3.head_bucket(Bucket=name)
    except Exception:  # noqa: BLE001
        kwargs = {} if region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": region}}
        s3.create_bucket(Bucket=name, **kwargs)
        s3.put_public_access_block(Bucket=name, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
        print(f"Bucket d'artefacts créé: {name}")
    return name


def outputs(c: dict[str, str], quiet: bool = False) -> dict[str, str]:
    stacks = boto("cloudformation").describe_stacks(StackName=c["stack"])["Stacks"]
    out = {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}
    OUTPUTS_FILE.parent.mkdir(exist_ok=True)
    OUTPUTS_FILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    if not quiet:
        for k, v in out.items():
            print(f"{k:<16} {v}")
    return out


def cmd_deploy(c: dict[str, str]) -> None:
    provider = os.environ.get("LLM_PROVIDER", "bedrock")
    model = os.environ.get("BEDROCK_MODEL_ID", "")
    if provider == "bedrock" and not model:
        raise SystemExit("BEDROCK_MODEL_ID manquant (voir docs/AWS_STATUS.md).")
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_lambda import build

    build()
    bucket = artifacts_bucket(c["region"])
    print("Package CloudFormation...")
    aws("cloudformation", "package", "--template-file", str(TEMPLATE), "--s3-bucket", bucket,
        "--s3-prefix", c["stack"], "--output-template-file", str(PACKAGED), "--region", c["region"])
    params = {
        "LlmProvider": provider,
        "BedrockModelId": model or "none",
        "BedrockFoundationModelId": foundation_model_of(model) if model else "none",
        "AppVersion": git_version(),
        "BudgetEmail": os.environ.get("BUDGET_EMAIL", ""),
    }
    print(f"Déploiement de la pile {c['stack']} ({c['region']}), modèle {model or '-'}... (CloudFront: 3 à 5 min la 1re fois)")
    aws("cloudformation", "deploy", "--template-file", str(PACKAGED), "--stack-name", c["stack"],
        "--capabilities", "CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND", "--no-fail-on-empty-changeset",
        "--region", c["region"], "--tags", "project=alphaforge",
        "--parameter-overrides", *[f"{k}={v}" for k, v in params.items()], capture=False)
    out = outputs(c, quiet=True)
    cmd_upload_data(c, out)
    _recycle_function(out["FunctionName"])
    outputs(c)


def _recycle_function(fn: str) -> None:
    """Touch an env var so every warm container re-reads the data from S3 at its next cold start."""
    lam = boto("lambda")
    conf = lam.get_function_configuration(FunctionName=fn)
    env = conf.get("Environment", {}).get("Variables", {})
    env["DATA_REFRESHED_AT"] = str(int(time.time()))
    lam.update_function_configuration(FunctionName=fn, Environment={"Variables": env})
    lam.get_waiter("function_updated_v2").wait(FunctionName=fn)


def cmd_upload_data(c: dict[str, str], out: dict[str, str] | None = None) -> None:
    out = out or outputs(c, quiet=True)
    bucket = out["DataBucketName"]
    s3 = boto("s3")
    n = 0
    data = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    for f in sorted(data.glob("*.csv")):
        s3.upload_file(str(f), bucket, f"starter/{f.name}", ExtraArgs={"ContentType": "text/csv"})
        n += 1
    prefix = os.environ.get("SNAPSHOT_PREFIX", "snapshots/")
    for f in sorted((data / "snapshots").glob("*.json")):
        s3.upload_file(str(f), bucket, f"{prefix}{f.name}", ExtraArgs={"ContentType": "application/json"})
        n += 1
    print(f"Données envoyées: {n} fichiers -> s3://{bucket}/starter/ et /{prefix}")


def cmd_deploy_web(c: dict[str, str]) -> None:
    out = outputs(c, quiet=True)
    web = ROOT / "web"
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm introuvable.")
    env = {**os.environ, "VITE_API_URL": out["ApiUrl"], "VITE_MOCK": "0", "VITE_AUTH": "cognito",
           "VITE_COGNITO_REGION": c["region"], "VITE_COGNITO_CLIENT_ID": out["UserPoolClientId"]}
    if not (web / "node_modules").exists():
        subprocess.run([npm, "ci"], cwd=web, check=True, env=env)
    subprocess.run([npm, "run", "build"], cwd=web, check=True, env=env)
    dist = web / "dist"
    bucket = out["WebBucketName"]
    s3 = boto("s3")
    local = {p.relative_to(dist).as_posix(): p for p in dist.rglob("*") if p.is_file()}
    for key, path in local.items():
        ctype = mimetypes.guess_type(key)[0] or "application/octet-stream"
        cache = "no-cache" if key.endswith(".html") else "public, max-age=31536000, immutable"
        s3.upload_file(str(path), bucket, key, ExtraArgs={"ContentType": ctype, "CacheControl": cache})
    stale = [o["Key"] for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket)
             for o in page.get("Contents", []) if o["Key"] not in local]
    for i in range(0, len(stale), 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in stale[i:i + 1000]]})
    boto("cloudfront").create_invalidation(DistributionId=out["DistributionId"], InvalidationBatch={
        "Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": str(time.time())})
    print(f"Site publié ({len(local)} fichiers, {len(stale)} retirés), cache invalidé: {out['WebUrl']}")


def _empty_bucket(name: str) -> None:
    s3 = boto("s3")
    for page in s3.get_paginator("list_object_versions").paginate(Bucket=name):
        objs = [{"Key": o["Key"], "VersionId": o["VersionId"]} for o in page.get("Versions", []) + page.get("DeleteMarkers", [])]
        if objs:
            s3.delete_objects(Bucket=name, Delete={"Objects": objs})


def cmd_destroy(c: dict[str, str], yes: str | None) -> None:
    out = outputs(c, quiet=True)
    print(f"ATTENTION: supprime la pile « {c['stack']} » ({c['region']}), le site, l'API et les buckets "
          f"{out.get('DataBucketName')}, {out.get('WebBucketName')} et {out.get('UserDataBucketName')} avec leur contenu, "
          f"ainsi que les comptes Cognito et la table {out.get('UserDataTableName')}.")
    answer = yes if yes is not None else (input(f"Tape le nom de la pile ({c['stack']}) pour confirmer: ")
                                          if sys.stdin.isatty() else "")
    if answer != c["stack"]:
        raise SystemExit("Annulé (confirmation absente ou différente).")
    for key in ("DataBucketName", "WebBucketName", "UserDataBucketName"):
        if out.get(key):
            _empty_bucket(out[key])
    aws("cloudformation", "delete-stack", "--stack-name", c["stack"], "--region", c["region"])
    aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", c["stack"], "--region", c["region"])
    print("Pile supprimée.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["deploy", "upload-data", "deploy-web", "outputs", "destroy"])
    p.add_argument("--confirm", help="destroy only: the stack name, for a non-interactive confirmation")
    a = p.parse_args()
    load_dotenv()
    c = cfg()
    if a.command == "deploy":
        cmd_deploy(c)
    elif a.command == "upload-data":
        cmd_upload_data(c)
    elif a.command == "deploy-web":
        cmd_deploy_web(c)
    elif a.command == "outputs":
        outputs(c)
    else:
        cmd_destroy(c, a.confirm)


if __name__ == "__main__":
    main()
