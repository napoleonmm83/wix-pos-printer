# 11. Infrastruktur und Deployment
Der Deployment-Prozess ist via GitHub Actions und einem Self-Hosted Runner auf dem Raspberry Pi vollständig automatisiert. Ein Rollback erfolgt durch einen `git revert` und anschliessenden Push.
