import base64
import os
import json
import sys,subprocess

CACHE_DIR = "./tmp/gcp-output"
os.makedirs(CACHE_DIR, exist_ok=True)

def cache_path(cmd):
    output_path = base64.urlsafe_b64encode(cmd.encode()).decode("utf-8")
    output_path = os.path.join(CACHE_DIR, output_path)
    return output_path

def gcs_cmd(cmd):
    """executes a 'gcloud' command returning a map of result data.
    successful results are cached in the `CACHE_DIR`."""

    cmd = "gcloud --format json " + cmd
    output_path = cache_path(cmd)
    
    if os.path.exists(output_path):
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
        print(result)
        raise

    return {"cmd": cmd, "rc": rc, "data": data, "stdout": stdout, "stderr": stderr}
    

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
    data = gcs_cmd("projects list")["data"]
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
    data = gcs_cmd(f"projects get-iam-policy {project_id}")["data"]
    member_list = []
    for binding in data.get("bindings", []):
        for member in binding["members"]:
            if member.startswith("user:"):
                member = member[len("user:"):]
            member_list.append(member)
    return member_list

def main():
    for project_id in project_list():
        print(f"--- {project_id}")
        [print(m) for m in project_members(project_id)]
        print()
    return 0

if __name__ == '__main__':
    sys.exit(main())
