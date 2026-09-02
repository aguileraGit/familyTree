FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Portainer's git-stack deployment does not preserve a .git directory in the
# build context (confirmed: `git status` inside this container reports "not
# a git repository"), so `git rev-parse` never works here. Instead, ask
# GitHub's API directly for the latest commit SHA on the branch being
# deployed.
ARG GITHUB_REPO=aguileraGit/familyTree
ARG GITHUB_BRANCH=master
RUN curl -sf "https://api.github.com/repos/${GITHUB_REPO}/commits/${GITHUB_BRANCH}" \
        | grep -m1 '"sha"' | cut -d '"' -f4 | cut -c1-7 > GIT_SHA \
    || echo unknown > GIT_SHA

EXPOSE 5001

CMD ["python", "app.py"]