import json
import datetime as dt
import requests
import re
import urllib3
from collections import defaultdict
from requests.auth import HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JENKINS_URL = "https://alm-latam-assurance.dev.echonet/jenkins"
JENKINS_USER = "j13399"
JENKINS_API_TOKEN = "TU_TOKEN_JENKINS"

BITBUCKET_URL = "https://devops-latam-assurance.is.echonet/git"
BITBUCKET_TOKEN = "TU_TOKEN_BITBUCKET"

DAYS_BACK = 30
MAX_LEAD_TIME_HOURS = 720

ROOT_VIEW = "view/Devops LAM"
ROOT_FOLDER = "Centralized_DevOps_LAM"

PROXY = {
    "http": "http://172.17.89.1:8080",
    "https": "http://172.17.89.1:8080",
}
PROXY = {k: v for k, v in PROXY.items() if v}

AUTH = HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN)

# =========================================================
# JENKINS NAV
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
# FILTROS
# =========================================================
def is_master_job(job_url):
    return job_url.strip("/").split("/")[-1].lower() == "master"


def extract_country(job_url):
    try:
        parts = job_url.split("/job/")
        for i, part in enumerate(parts):
            if ROOT_FOLDER in part:
                return parts[i + 1].split("/")[0]
    except:
        pass
    return "Unknown"


# =========================================================
# BUILDS
# =========================================================
def fetch_builds(job_url):
    url = f"{job_url}/api/json?tree=builds[number,result,timestamp]"
    r = requests.get(url, auth=AUTH, proxies=PROXY, verify=False)
    r.raise_for_status()
    return r.json().get("builds", [])


# =========================================================
# 🔥 NUEVA FUNCION CORREGIDA
# =========================================================
def count_pipeline_executions_by_country(all_jobs):
    data = defaultdict(lambda: {
        "dev": 0,
        "qa": 0,
        "master": 0,
        "securitygate": 0
    })

    for job in all_jobs:
        try:
            country = extract_country(job)

            # 👇 pipeline REAL (último segmento)
            pipeline_name = job.strip("/").split("/")[-1].lower()

            if pipeline_name not in ["dev", "qa", "master", "securitygate"]:
                continue

            builds = fetch_builds(job)
            data[country][pipeline_name] += len(builds)

        except:
            continue

    return data


# =========================================================
# GIT
# =========================================================
def extract_git_info(build_json):
    for action in build_json.get("actions", []):
        if action.get("_class") == "hudson.plugins.git.util.BuildData":
            sha = action.get("lastBuiltRevision", {}).get("SHA1")
            repo_url = action.get("remoteUrls", [None])[0]

            if sha and repo_url:
                match = re.search(r"/scm/([^/]+)/(.+)\.git", repo_url)
                if match:
                    return {
                        "sha": sha,
                        "project": match.group(1),
                        "repo": match.group(2)
                    }
    return None


def get_commit_timestamp(project, repo, sha):
    url = f"{BITBUCKET_URL}/rest/api/latest/projects/{project}/repos/{repo}/commits/{sha}"
    headers = {"Authorization": f"Bearer {BITBUCKET_TOKEN}"}

    try:
        r = requests.get(url, headers=headers, verify=False)
        r.raise_for_status()
        return r.json().get("authorTimestamp")
    except:
        return None


# =========================================================
# LEAD TIME
# =========================================================
def calculate_lead_time(builds, job_url):
    times = []

    for b in builds:
        if b.get("result") != "SUCCESS":
            continue

        try:
            url = f"{job_url}/{b['number']}/api/json"
            r = requests.get(url, auth=AUTH, proxies=PROXY, verify=False)
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

        except:
            continue

    return round(sum(times) / len(times), 2) if times else 0


# =========================================================
# MTTR
# =========================================================
def calculate_mttr(builds, job_url):
    commit_map = {}

    for b in builds:
        try:
            url = f"{job_url}/{b['number']}/api/json"
            r = requests.get(url, auth=AUTH, proxies=PROXY, verify=False)
            r.raise_for_status()

            detail = r.json()
            git = extract_git_info(detail)

            if not git:
                continue

            sha = git["sha"]

            if sha not in commit_map:
                commit_map[sha] = []

            commit_map[sha].append({
                "timestamp": detail["timestamp"],
                "result": detail["result"]
            })

        except:
            continue

    mttr_list = []

    for sha, build_list in commit_map.items():
        build_list = sorted(build_list, key=lambda x: x["timestamp"])

        fail_time = None

        for b in build_list:
            if b["result"] != "SUCCESS":
                if fail_time is None:
                    fail_time = b["timestamp"]
            elif fail_time:
                mttr = b["timestamp"] - fail_time
                mttr_list.append(mttr)
                break

    return round(sum(mttr_list) / len(mttr_list) / 1000 / 3600, 2) if mttr_list else 0


# =========================================================
# MAIN
# =========================================================
def main():

    root_url = f"{JENKINS_URL}/{ROOT_VIEW}/job/{ROOT_FOLDER}"

    all_jobs = get_all_jobs_recursive(root_url)
    prod_jobs = [j for j in all_jobs if is_master_job(j)]

    pipeline_counts = count_pipeline_executions_by_country(all_jobs)

    country_data = defaultdict(lambda: {
        "builds": [],
        "lead_times": [],
        "jobs": []
    })

    for job in prod_jobs:
        country = extract_country(job)

        try:
            builds = fetch_builds(job)

            builds = [
                b for b in builds
                if (dt.datetime.now() - dt.datetime.fromtimestamp(b["timestamp"] / 1000)).days <= DAYS_BACK
            ]

            country_data[country]["builds"].extend(builds)
            country_data[country]["jobs"].append(job)

            lt = calculate_lead_time(builds, job)
            if lt > 0:
                country_data[country]["lead_times"].append(lt)

        except:
            continue

    countries_output = []

    for country, data in country_data.items():
        builds = data["builds"]

        success = [b for b in builds if b["result"] == "SUCCESS"]
        failed = [b for b in builds if b["result"] != "SUCCESS"]

        failure_rate = (len(failed) / len(builds) * 100) if builds else 0

        mttr_values = []
        for job in data["jobs"]:
            job_builds = fetch_builds(job)
            mttr_val = calculate_mttr(job_builds, job)
            if mttr_val > 0:
                mttr_values.append(mttr_val)

        mttr = round(sum(mttr_values) / len(mttr_values), 2) if mttr_values else 0

        lead_time_hours = round(sum(data["lead_times"]) / len(data["lead_times"]), 2) if data["lead_times"] else 0
        lead_time_days = round(lead_time_hours / 24, 2)

        deployments_per_week = round(len(success) / (DAYS_BACK / 7), 2)

        countries_output.append({
            "name": country,
            "pipeline_executions": pipeline_counts.get(country, {
                "dev": 0,
                "qa": 0,
                "master": 0,
                "securitygate": 0
            }),
            "deployment_frequency": deployments_per_week,
            "lead_time": lead_time_days,
            "mttr": mttr,
            "failure_rate": round(failure_rate, 2)
        })

    dora_data = {
        "generated_at": dt.datetime.now().isoformat(),
        "countries": countries_output
    }

    with open("dora-summary.json", "w") as f:
        json.dump(dora_data, f, indent=2)

    print("\n✅ Archivo generado: dora-summary.json\n")


if __name__ == "__main__":
    main()