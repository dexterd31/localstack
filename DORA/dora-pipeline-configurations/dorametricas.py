import json
import datetime as dt
import requests
import re
from requests.auth import HTTPBasicAuth

# =========================================================
# 🔧 CONFIG
# =========================================================
JENKINS_URL = "https://alm-latam-assurance.dev.echonet/jenkins"
JENKINS_USER = "j13399"
JENKINS_API_TOKEN = "TU_TOKEN_JENKINS"

BITBUCKET_URL = "https://devops-latam-assurance.is.echonet/git"
BITBUCKET_TOKEN = "TU_TOKEN_BITBUCKET"

DAYS_BACK = 30

COUNTRY_FOLDERS = [
    "view/Chile",
    "view/Automation",
    "view/Colombia",
    "view/Devops LAM",
    "view/KAFKA",
    "view/LAM Microservices",
    "view/PIMS",
    "view/PreProd-Chile"
]

# =========================================================
# 🌐 PROXY
# =========================================================
PROXY = {
    "http": "http://172.17.89.1:8080",
    "https": "http://172.17.89.1:8080",
}
PROXY = {k: v for k, v in PROXY.items() if v}

# =========================================================
# 🔐 AUTH
# =========================================================
AUTH = HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN)

# =========================================================
# 📡 JENKINS
# =========================================================
def get_view_jobs(view: str):
    url = f"{JENKINS_URL}/{view}/api/json?tree=jobs[name,url,_class]"
    r = requests.get(url, auth=AUTH, proxies=PROXY)
    r.raise_for_status()
    return r.json().get("jobs", [])


def get_all_jobs(job_url: str):
    jobs = []
    url = f"{job_url}/api/json?tree=jobs[name,url,_class]"
    r = requests.get(url, auth=AUTH, proxies=PROXY)
    r.raise_for_status()

    for item in r.json().get("jobs", []):
        if "Folder" in item.get("_class", ""):
            jobs.extend(get_all_jobs(item["url"]))
        else:
            jobs.append(item["url"])

    return jobs


def get_jobs_from_view(view: str):
    jobs = []
    for item in get_view_jobs(view):
        if "Folder" in item.get("_class", ""):
            jobs.extend(get_all_jobs(item["url"]))
        else:
            jobs.append(item["url"])
    return jobs


def fetch_all_builds(job_url: str):
    url = f"{job_url}/api/json?tree=builds[number,result,timestamp]"
    r = requests.get(url, auth=AUTH, proxies=PROXY)
    r.raise_for_status()
    return r.json().get("builds", [])


# =========================================================
# 🧠 GIT INFO DESDE JENKINS
# =========================================================
def extract_git_info(build_json):
    for action in build_json.get("actions", []):

        if action.get("_class") == "hudson.plugins.git.util.BuildData":

            sha = None
            if "lastBuiltRevision" in action:
                sha = action["lastBuiltRevision"].get("SHA1")

            repo_url = None
            if "remoteUrls" in action and action["remoteUrls"]:
                repo_url = action["remoteUrls"][0]

            if sha and repo_url:
                match = re.search(r"/scm/([^/]+)/(.+)\.git", repo_url)

                if match:
                    return {
                        "sha": sha,
                        "project": match.group(1),
                        "repo": match.group(2)
                    }

    return None


# =========================================================
# 🌐 BITBUCKET
# =========================================================
def get_commit_timestamp(project, repo, sha):
    url = f"{BITBUCKET_URL}/rest/api/latest/projects/{project}/repos/{repo}/commits/{sha}"

    headers = {
        "Authorization": f"Bearer {BITBUCKET_TOKEN}"
    }

    try:
        r = requests.get(url, headers=headers, verify=False)
        r.raise_for_status()

        data = r.json()
        return data.get("authorTimestamp")

    except Exception as e:
        print(f"⚠️ Error commit {sha}: {e}")
        return None


# =========================================================
# ⏱️ LEAD TIME
# =========================================================
def calculate_lead_time(builds, job_url):
    lead_times = []

    for b in builds:
        if b.get("result") != "SUCCESS":
            continue

        try:
            build_number = b["number"]
            build_url = f"{job_url}/{build_number}/api/json"

            r = requests.get(build_url, auth=AUTH, proxies=PROXY)
            r.raise_for_status()

            build_detail = r.json()

            git_info = extract_git_info(build_detail)

            if not git_info:
                continue

            commit_ts = get_commit_timestamp(
                git_info["project"],
                git_info["repo"],
                git_info["sha"]
            )

            if not commit_ts:
                continue

            build_ts = build_detail["timestamp"]

            lead_time = (build_ts - commit_ts) / 1000 / 3600
            lead_times.append(lead_time)

        except Exception as e:
            print(f"⚠️ Error en build {b.get('number')}: {e}")

    if not lead_times:
        return 0

    return round(sum(lead_times) / len(lead_times), 2)


# =========================================================
# 🔧 MTTR
# =========================================================
def calculate_mttr(builds):
    builds_sorted = sorted(builds, key=lambda x: x["timestamp"])

    mttr_times = []
    failure_time = None

    for b in builds_sorted:
        if b.get("result") != "SUCCESS":
            if failure_time is None:
                failure_time = b["timestamp"]

        elif b.get("result") == "SUCCESS" and failure_time:
            recovery_time = b["timestamp"]
            mttr_times.append(recovery_time - failure_time)
            failure_time = None

    if not mttr_times:
        return 0

    return round(sum(mttr_times) / len(mttr_times) / 1000 / 3600, 2)


# =========================================================
# 📊 MÉTRICAS
# =========================================================
def calculate_metrics_for_view(view: str):
    print(f"\n🔍 Procesando {view}...")

    jobs = get_jobs_from_view(view)

    all_builds = []
    all_lead_times = []

    for job in jobs:
        try:
            builds = fetch_all_builds(job)

            builds = [
                b for b in builds
                if (dt.datetime.now() - dt.datetime.fromtimestamp(b["timestamp"] / 1000)).days <= DAYS_BACK
            ]

            all_builds.extend(builds)

            lt = calculate_lead_time(builds, job)
            if lt > 0:
                all_lead_times.append(lt)

        except Exception as e:
            print(f"⚠️ Error en {job}: {e}")

    success = [b for b in all_builds if b.get("result") == "SUCCESS"]
    failed = [b for b in all_builds if b.get("result") != "SUCCESS"]

    deploys_per_day = {}
    for b in success:
        d = dt.datetime.fromtimestamp(b["timestamp"] / 1000).strftime("%Y-%m-%d")
        deploys_per_day[d] = deploys_per_day.get(d, 0) + 1

    mttr = calculate_mttr(all_builds)

    lead_time_final = round(sum(all_lead_times) / len(all_lead_times), 2) if all_lead_times else 0

    metrics = {
        "view": view,
        "total_jobs": len(jobs),
        "total_builds": len(all_builds),
        "deployments": len(success),
        "failure_rate": (len(failed) / len(all_builds) * 100) if all_builds else 0,
        "mttr_hours": mttr,
        "lead_time_hours": lead_time_final,
        "deploys_per_day": deploys_per_day
    }

    # 🔥 DASHBOARD LOG
    print(f"""
📊 ===== {view} =====
Jobs: {metrics['total_jobs']}
Builds: {metrics['total_builds']}
Deployments: {metrics['deployments']}
Failure Rate: {metrics['failure_rate']:.2f}%
MTTR (hrs): {metrics['mttr_hours']}
Lead Time (hrs): {metrics['lead_time_hours']}
========================
""")

    return metrics


# =========================================================
# 🚀 MAIN
# =========================================================
def main():
    for view in COUNTRY_FOLDERS:
        try:
            calculate_metrics_for_view(view)
        except Exception as e:
            print(f"❌ Error en {view}: {e}")

    print("\n✅ Ejecución finalizada.")


if __name__ == "__main__":
    main()  