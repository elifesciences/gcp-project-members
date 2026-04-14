# gcp-project-members

Small python scripts to list GCP (Google Cloud Provider) projects, their members and remove users across all projects.


## requires

* Python 3.6+
* gcloud

## Get a list of projects with their members
```
gcloud auth login
python gcp_project_members.py
```

See `./update.sh` how to log in if you need to open the browser manually.

## Remove user across all projects

```
python remove_gcp_project_members.py their-email-address@example.com
```

## licence

[MIT licensed](./LICENCE).
