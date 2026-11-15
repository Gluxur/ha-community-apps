## Add an app repository

File: `catalog/repositories/<owner>/<repo>.yaml` containing only:

```yaml
repository: owner/repo
```

- [ ] I am the owner or a maintainer of this repository.
- [ ] This pull request changes only that one file.

What happens next:

1. A workflow scans the repository and posts a report: permissions each app requests
   (`full_access`, `privileged`, `docker_api`, `host_network`, write access to `/config`…),
   risk level, prebuilt image or built from source, domains found in the code, and the
   domains looked up when the app is started for a few minutes in an isolated network.
2. A reviewer reads the report and the repository, then merges or asks questions.
3. After merge, the entry is recorded as reviewed and appears in the catalog.
4. Every night, repositories that changed are rescanned. New permissions, a higher risk or
   new domains put the entry back in review (`flagged`) until a reviewer looks at it.
