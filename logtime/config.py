import os

api_key = os.environ.get("LOGTIME_REDMINE_API_KEY")
redmine_url = os.environ.get("LOGTIME_REDMINE_URL")
root_folder = "~/logtime"
defaults = {
    "sync": "77549",
    "rezie": "77549",
    "organization": "77549",
    "standup": "77488",
    "refinement": "77548",
    "refinement priprava": "77548",
    "review": "77489",
    "review priprava": "77489",
    "retro": "77489",
    "retrospektiva": "77489",
    "retrospektiva priprava": "77489",
    "planning": "77491",
    "planning priprava": "77491",
    "kontrola prostredi": "77546",
    "cop": "77422",
    "CoP": "77422",
    "CoP priprava": "80565",
    "cop priprava": "80565",
}
