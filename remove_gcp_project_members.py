import base64
import os
import json
import sys,subprocess
import time
import random

MAX_RETRIES = 5
INITIAL_DELAY = 2
MAX_DELAY = 120

CACHE_DIR = "./tmp/gcp-output"
os.makedirs(CACHE_DIR, exist_ok=True)

def cache_path(cmd):
    output_path = base64.urlsafe_b64encode(cmd.encode()).decode("utf-8")
    output_path = os.path.join(CACHE_DIR, output_path)
    return output_path


def gcs_cmd(cmd, use_cache=True):
    """executes a 'gcloud' command returning a map of result data.
    successful results are cached in the `CACHE_DIR`. Does not retry on failure."""

    cmd = "gcloud --format json " + cmd
    output_path = cache_path(cmd)

    if use_cache and os.path.exists(output_path):
        with open(output_path, "r") as fh:
            return {"cmd": cmd, "rc": -1, "data": json.load(fh), "stdout": None, "stderr": None}

    result = subprocess.run(cmd, shell=True, capture_output=True)
    rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    try:
        json_str = stdout.decode("utf-8")
        data = json.loads(json_str)
        with open(output_path, "w") as fh:
            fh.write(json_str)
    except json.decoder.JSONDecodeError as err:
        raise Exception(f"Failed to parse JSON output: {result}")

    return {"cmd": cmd, "rc": rc, "data": data, "stdout": stdout, "stderr": stderr}


def gcs_cmd_with_retry(cmd):
    """Execute gcloud command with exponential backoff retry on rate limit errors."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            result = gcs_cmd(cmd, use_cache=False)
            if result["rc"] == 0:
                return result
            stderr = result["stderr"].decode("utf-8") if result["stderr"] else ""
            if "RESOURCE_EXHAUSTED" in stderr or "429" in stderr:
                delay = min(INITIAL_DELAY * (2 ** attempt), MAX_DELAY)
                jitter = random.uniform(-1, 1)
                wait_time = max(0, delay + jitter)
                print(f"  Rate limited, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                time.sleep(wait_time)
                last_error = Exception(f"Rate limited: {stderr}")
                continue
            return result
        except Exception as e:
            last_error = e
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                delay = min(INITIAL_DELAY * (2 ** attempt), MAX_DELAY)
                jitter = random.uniform(-1, 1)
                wait_time = max(0, delay + jitter)
                print(f"  Rate limited, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                time.sleep(wait_time)
                continue
            raise
    raise last_error


def project_list():
    """looks like:
[
  ...
  {
    "createTime": "2015-01-01T00:00:00.000Z",
    "lifecycleState": "ACTIVE",
    "name": "Analytics Access",
    "projectId": "foo-bar-987654",
    "projectNumber": "1234567890"
  }
]
    """
    data = gcs_cmd_with_retry("projects list")["data"]
    return [struct["projectId"] for struct in data]

def project_members(project_id):
    """
{'bindings': [{'members': ['serviceAccount:foo@bar.gserviceaccount.com'],
               'role': 'roles/iam.serviceAccountKeyAdmin'},
              {'members': ['user:foo.bar@elifesciences.org',
                           'user:bar.baz@elifesciences.org',
                           ...
                           'user:bup.boo@elifesciences.org'],
               'role': 'roles/owner'},
              {'members': ['serviceAccount:boo@foo.iam.gserviceaccount.com'],
               'role': 'roles/viewer'}],
 'etag': 'BwW7csbHcZM=',
 'version': 1}
    """
    data = gcs_cmd_with_retry(f"projects get-iam-policy {project_id}")["data"]
    member_list = []
    for binding in data.get("bindings", []):
        for member in binding["members"]:
            if member.startswith("user:"):
                member = member[len("user:"):]
            member_list.append((member, binding["role"]))
    return member_list

def main():
    if len(sys.argv) != 2:
        print("ERROR: pass a user's email address as the first argument")
        return 1
    user_email = sys.argv[1]
    projects = project_list()
    print(f"Processing {len(projects)} projects...")
    for idx, project_id in enumerate(projects, 1):
        print(f"[{idx}/{len(projects)}] {project_id}")
        for m in project_members(project_id):
            if user_email == m[0]:
                result = gcs_cmd_with_retry(f"projects remove-iam-policy-binding {project_id} --member=user:{user_email} --role={m[1]}")
                stderr = result["stderr"].decode("utf-8") if result["stderr"] else ""
                if "Updated" in stderr or "Removed" in stderr:
                    print(f"  Removed {user_email} from {project_id} as {m[1]}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
