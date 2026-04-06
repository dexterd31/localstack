import datetime as dt
import requests
import re
import urllib3
from requests.auth import HTTPBasicAuth

# =========================================================
# 🔇 OCULTAR WARNINGS SSL
# =========================================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================================================
# 🔧 CONFIG
# =========================================================
JENKINS_URL = "https://alm-latam-assurance.dev.echonet/jenkins"
JENKINS_USER = "j13399"
JENKINS_API_TOKEN = "TU_TOKEN_JENKINS"

BITBUCKET_URL = "https://devops-latam-assurance.is.echonet/git"
BITBUCKET_TOKEN = "TU_TOKEN_BITBUCKET"

DAYS_BACK = 30
MAX_LEAD_TIME_HOURS = 720  # 30 días

ROOT_VIEW = "view/Devops LAM"
ROOT_FOLDER = "Centralized_DevOps_LAM"

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
# 📡 JENKINS NAV
# =========================================================
def get_jobs(url):
    api = f"{url}/api/json?tree=jobs[name,url,_class]"
    r = requests.get(api, auth=AUTH, proxies=PROXY, verify=False)
    r.raise_for_status()
    return r.json().get("jobs", [])


def get_all_jobs_recursive(url):
    jobs = []

    for item in get_jobs(url):
        if "Folder" in item.get("_class", ""):
            jobs.extend(get_all_jobs_recursive(item["url"]))
        else:
            jobs.append(item["url"])

    return jobs


# =========================================================
# 🎯 FILTRO PRODUCCIÓN
# =========================================================
def is_master_job(job_url):
    return "/master" in job_url.lower()


# =========================================================
# 📦 BUILDS
# =========================================================
def fetch_builds(job_url):
    url = f"{job_url}/api/json?tree=builds[number,result,timestamp]"
    r = requests.get(url, auth=AUTH, proxies=PROXY, verify=False)
    r.raise_for_status()
    return r.json().get("builds", [])


# =========================================================
# 🧠 GIT INFO
# =========================================================
def extract_git_info(build_json):
    for action in build_json.get("actions", []):
        if action.get("_class") == "hudson.plugins.git.util.BuildData":

            sha = action.get("lastBuiltRevision", {}).get("SHA1")

            repo_url = None
            if action.get("remoteUrls"):
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
        return r.json().get("authorTimestamp")
    except:
        return None


# =========================================================
# ⏱️ LEAD TIME
# =========================================================
def calculate_lead_time(builds, job_url):
    times = []

    for b in builds:
        if b.get("result") != "SUCCESS":
            continue

        try:
            build_url = f"{job_url}/{b['number']}/api/json"
            r = requests.get(build_url, auth=AUTH, proxies=PROXY, verify=False)
            r.raise_for_status()

            detail = r.json()
            git = extract_git_info(detail)

            if not git:
                continue

            commit_ts = get_commit_timestamp(git["project"], git["repo"], git["sha"])
            if not commit_ts:
                continue

            build_ts = detail["timestamp"]
            lt = (build_ts - commit_ts) / 1000 / 3600

            if 0 < lt <= MAX_LEAD_TIME_HOURS:
                times.append(lt)

        except Exception as e:
            print(f"⚠️ LeadTime error build {b['number']}: {e}")

    return round(sum(times) / len(times), 2) if times else 0


# =========================================================
# 🔧 MTTR
# =========================================================
def calculate_mttr(builds):
    builds = sorted(builds, key=lambda x: x["timestamp"])

    mttr = []
    fail_time = None

    for b in builds:
        if b["result"] != "SUCCESS":
            if fail_time is None:
                fail_time = b["timestamp"]

        elif fail_time:
            mttr.append(b["timestamp"] - fail_time)
            fail_time = None

    return round(sum(mttr) / len(mttr) / 1000 / 3600, 2) if mttr else 0


# =========================================================
# 🚀 MAIN LOGIC
# =========================================================
def main():

    root_url = f"{JENKINS_URL}/{ROOT_VIEW}/job/{ROOT_FOLDER}"

    print(f"\n🔍 Procesando estructura centralizada...\n")

    all_jobs = get_all_jobs_recursive(root_url)

    # 🔥 SOLO MASTER
    prod_jobs = [j for j in all_jobs if is_master_job(j)]

    print(f"🎯 Jobs de producción encontrados: {len(prod_jobs)}")

    all_builds = []
    lead_times = []

    for job in prod_jobs:
        try:
            builds = fetch_builds(job)

            builds = [
                b for b in builds
                if (dt.datetime.now() - dt.datetime.fromtimestamp(b["timestamp"] / 1000)).days <= DAYS_BACK
            ]

            all_builds.extend(builds)

            lt = calculate_lead_time(builds, job)
            if lt > 0:
                lead_times.append(lt)

        except Exception as e:
            print(f"⚠️ Error job {job}: {e}")

    success = [b for b in all_builds if b["result"] == "SUCCESS"]
    failed = [b for b in all_builds if b["result"] != "SUCCESS"]

    failure_rate = (len(failed) / len(all_builds) * 100) if all_builds else 0
    mttr = calculate_mttr(all_builds)
    lead_time = round(sum(lead_times) / len(lead_times), 2) if lead_times else 0

    # =====================================================
    # 📊 DASHBOARD FINAL
    # =====================================================
    print(f"""
📊 ===== DEVOPS LAM (PRODUCCIÓN REAL) =====
Jobs (master): {len(prod_jobs)}
Builds: {len(all_builds)}
Deployments: {len(success)}
Failure Rate: {failure_rate:.2f}%
MTTR (hrs): {mttr}
Lead Time (hrs): {lead_time}
===========================================
""")


if __name__ == "__main__":
    main()