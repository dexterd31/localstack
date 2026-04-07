import json
import datetime as dt
import requests
import re
import urllib3
from collections import defaultdict
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
MAX_LEAD_TIME_HOURS = 720

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
# 🎯 FILTROS
# =========================================================
def is_master_job(job_url):
    return "/master" in job_url.lower()


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
# 📦 BUILDS
# =========================================================
def fetch_builds(job_url):
    url = f"{job_url}/api/json?tree=builds[number,result,timestamp]"
    r = requests.get(url, auth=AUTH, proxies=PROXY, verify=False)
    r.raise_for_status()
    return r.json().get("builds", [])


# =========================================================
# 📊 TOTAL DEPLOYMENTS GLOBAL
# =========================================================
def count_total_deployments(all_jobs):
    total = 0
    for job in all_jobs:
        try:
            builds = fetch_builds(job)
            total += len(builds)
        except:
            continue
    return total


# =========================================================
# 📊 DEPLOYMENTS POR PAIS Y PIPELINE
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
            job_lower = job.lower()

            pipeline_type = None
            if "/dev" in job_lower:
                pipeline_type = "dev"
            elif "/qa" in job_lower:
                pipeline_type = "qa"
            elif "/master" in job_lower:
                pipeline_type = "master"
            elif "securitygate" in job_lower:
                pipeline_type = "securitygate"

            if not pipeline_type:
                continue

            builds = fetch_builds(job)
            data[country][pipeline_type] += len(builds)

        except:
            continue

    return data


# =========================================================
# 🧠 GIT INFO
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


# =========================================================
# 🌐 BITBUCKET
# =========================================================
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
# ⏱️ LEAD TIME
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
# 🔧 MTTR
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
# 🎯 PERFORMANCE
# =========================================================
def classify_performance(days):
    if days < 1:
        return "Élite"
    elif days < 7:
        return "Alto"
    elif days < 30:
        return "Medio"
    else:
        return "Bajo"


# =========================================================
# 🚀 MAIN
# =========================================================
def main():

    root_url = f"{JENKINS_URL}/{ROOT_VIEW}/job/{ROOT_FOLDER}"

    all_jobs = get_all_jobs_recursive(root_url)
    prod_jobs = [j for j in all_jobs if is_master_job(j)]

    total_deployments_global = count_total_deployments(all_jobs)
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
    all_lead_days = []

    for country, data in country_data.items():
        builds = data["builds"]

        success = [b for b in builds if b["result"] == "SUCCESS"]
        failed = [b for b in builds if b["result"] != "SUCCESS"]

        failure_rate = (len(failed) / len(builds) * 100) if builds else 0

        mttr_values = []
        for job in data["jobs"]:
            job_builds = fetch_builds(job)
            job_builds = [
                b for b in job_builds
                if (dt.datetime.now() - dt.datetime.fromtimestamp(b["timestamp"] / 1000)).days <= DAYS_BACK
            ]
            mttr_val = calculate_mttr(job_builds, job)
            if mttr_val > 0:
                mttr_values.append(mttr_val)

        mttr = round(sum(mttr_values) / len(mttr_values), 2) if mttr_values else 0

        lead_time_hours = round(sum(data["lead_times"]) / len(data["lead_times"]), 2) if data["lead_times"] else 0
        lead_time_days = round(lead_time_hours / 24, 2)

        all_lead_days.append(lead_time_days)

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

    def avg(key):
        vals = [c[key] for c in countries_output if c[key] > 0]
        return round(sum(vals) / len(vals), 2) if vals else 0

    regional = {
        "deployment_frequency": {"value": avg("deployment_frequency"), "trend": {"direction": "up", "percent": 0}},
        "lead_time": {"value": avg("lead_time"), "trend": {"direction": "down", "percent": 0}},
        "mttr": {"value": avg("mttr"), "trend": {"direction": "down", "percent": 0}},
        "failure_rate": {"value": avg("failure_rate"), "trend": {"direction": "down", "percent": 0}}
    }

    levels = {"Élite": 0, "Alto": 0, "Medio": 0, "Bajo": 0}

    for lt in all_lead_days:
        level = classify_performance(lt)
        levels[level] += 1

    performance_distribution = {
        "labels": ["Élite", "Alto", "Medio", "Bajo"],
        "values": [levels["Élite"], levels["Alto"], levels["Medio"], levels["Bajo"]]
    }

    evolution = {
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "deployment_frequency": [3, 3.2, 3.5, 3.8, 3.6, 3.9],
        "lead_time": [2.5, 2.3, 2.2, 2.1, 2.0, 1.9],
        "failure_rate": [3.0, 2.8, 2.6, 2.4, 2.2, 2.0]
    }

    dora_data = {
        "generated_at": dt.datetime.now().isoformat(),
        "total_deployments": total_deployments_global,
        "regional": regional,
        "countries": countries_output,
        "evolution": evolution,
        "performance_distribution": performance_distribution
    }

    with open("dora-summary.json", "w") as f:
        json.dump(dora_data, f, indent=2)

    print("\n✅ Archivo generado: dora-summary.json\n")


if __name__ == "__main__":
    main()