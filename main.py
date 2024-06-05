from enum import Enum
import datetime
import json
import random

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

app = FastAPI(debug=True, title="InOutFatDogGym")


class Weekday(str, Enum):
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"
    saturday = "saturday"
    sunday = "sunday"


num_to_day = {0: Weekday.monday,
              1: Weekday.tuesday,
              2: Weekday.wednesday,
              3: Weekday.thursday,
              4: Weekday.friday,
              5: Weekday.saturday,
              6: Weekday.sunday}


def validate_time(time: datetime.time, weekday: int) -> datetime.time:
    weekday = num_to_day[weekday]
    with open("gym_config.json") as file:
        config = json.load(file)

    opening = str_to_time(config["schedule"][weekday]["opening"])
    closing = str_to_time(config["schedule"][weekday]["closing"])
    time = max(time, opening)
    time = min(time, closing)
    return time


def str_to_time(time_str: str) -> datetime.time:
    """
    "09:41:27" -> datetime.time(9,41,0) ignores seconds
    """
    return datetime.time(int(time_str[:2]), int(time_str[3:5]))


def str_to_date(time_str: str) -> datetime.date:
    """
    "2024-05-09" -> datetime.date(2024, 5, 9)
    """
    return datetime.date(int(time_str[:4]), int(time_str[5:7]), int(time_str[8:]))


@app.get("/")
async def read_root(request: Request):
    return RedirectResponse(f"{request.url}docs")


@app.get("/users/")
async def display_users(phone: str = None):
    with open("users.json", "r") as file:
        json_data = json.load(file)
    if phone is None:
        return json_data
    result = list(filter(lambda elem: elem["phone"] == phone, json_data))
    return result if result != list() else None


@app.get("/add_user/")
async def add_user(phone: str, duration: int):
    with open("users.json", "r") as file:
        json_data = json.load(file)
    end = datetime.date.today() + datetime.timedelta(days=duration * 30)
    json_data.append({"phone": phone, "u_id": json_data[-1]["u_id"] + 1, "admin_rights": 0, "end_date": str(end)})
    with open("users.json", "w") as file:
        json.dump(json_data, file, indent=2)


@app.get("/get_config/")
async def get_config():
    with open("gym_config.json", "r") as file:
        json_data = json.load(file)
    return json_data


# # id, time, status
@app.get("/create_tracking")
async def create_tracking(date: str):
    date = str_to_date(date)
    with open("users.json", "r") as file:
        users = json.load(file)
    res_json = []
    for user in users:
        if random.random() >= 0.3:  # Идет ли в зал в текущий день.
            continue
        if random.random() >= 0.3:  # Если вечерний.
            entry_time_s = int(random.gauss(18 * 60 * 60, 30 * 60))
        else:
            entry_time_s = int(random.gauss(12 * 60 * 60, 30 * 60))
        entry_time_s -= entry_time_s % 60
        exit_time_s = entry_time_s + int(random.expovariate(1 / 3600))
        exit_time_s -= exit_time_s % 60
        entry_time = datetime.time(entry_time_s // 3600, (entry_time_s % 3600) // 60)
        exit_time = datetime.time(exit_time_s // 3600, (exit_time_s % 3600) // 60)
        entry_time = validate_time(entry_time, date.weekday())
        exit_time = validate_time(exit_time, date.weekday())

        res_json.append({"u_id": user["u_id"],
                         "time": str(entry_time),
                         "status": "in"})

        res_json.append({"u_id": user["u_id"],
                         "time": str(exit_time),
                         "status": "out"})

    res_json.sort(key=lambda x: x["time"])
    with open("tracking.json") as file:
        tracked = json.load(file)
    tracked[str(date)] = res_json
    with open("tracking.json", "w") as file:
        json.dump(tracked, file, indent=2)
    return res_json


def get_tracking(date1: str, date2: str) -> dict:
    """
    По двум точкам возвращает записи о входах/выходах в зале.
    """
    with open("tracking.json", "r") as file:
        tracked = json.load(file)
    date1 = str_to_date(date1)
    date2 = str_to_date(date2)
    res = {}
    while date1 <= date2:
        res[str(date1)] = tracked[str(date1)]
        date1 += datetime.timedelta(days=1)
    return res


def count_visitors_number(gym: str, date: datetime.date, cur_time: datetime.time) -> (int, int):
    date_str = str(date)
    json_data = get_tracking(date_str, date_str)[date_str]

    res = 0
    res_in = 0
    for user in json_data:
        if cur_time < str_to_time(user["time"]):
            return res, res_in
        res += 1 if user["status"] == "in" else -1
        res_in += 1 if user["status"] == "in" else 0
    return res, res_in


@app.get("/process_visitors")
async def process_visitors(date: str, time: str, gym: str) -> dict:
    date = str_to_date(date)
    time = str_to_time(time)
    weekday = num_to_day[date.weekday()]
    if gym == "FatDogGym":
        with open("gym_config.json") as file:
            gym_config = json.load(file)
    else:
        raise ValueError("We cannot work with this gym")

    opening = str_to_time(gym_config["schedule"][weekday]["opening"])
    closing = str_to_time(gym_config["schedule"][weekday]["closing"])
    if opening <= time < closing:
        visitors_num, vis_in = count_visitors_number(gym, date, time)
        with open("processed_data.json") as file:
            processed_data = json.load(file)

        if gym not in processed_data:
            processed_data[gym] = dict()
            processed_data[gym]["load"] = dict()
        if str(date) not in processed_data[gym]["load"]:
            processed_data[gym]["load"][str(date)] = dict()
        processed_data[gym]["load"][str(date)][str(time)[:5]] = dict()
        processed_data[gym]["load"][str(date)][str(time)[:5]]["visitors_num"] = visitors_num
        processed_data[gym]["load"][str(date)]["visitors_sum"] = vis_in

        with open("processed_data.json", "w") as file:
            json.dump(processed_data, file, indent=2)
        return processed_data


@app.get("/get_processed_dates")
async def get_processed_dates(date1: str, date2: str, gym: str) -> list:
    with open("processed_data.json") as file:
        processed_load = json.load(file)[gym]["load"]
    if date1 == date2:
        return [processed_load[date1]]
    date1_ = str_to_date(date1)
    date2_ = str_to_date(date2)
    if date1_ > date2_:
        raise ValueError("date1 must be less or equal than date2")
    res = list()
    while date1_ < date2_:
        if str(date1_) in processed_load:
            res.append(processed_load[str(date1_)])
            res[-1]["date"] = str(date1_)[-2:]
        date1_ += datetime.timedelta(days=1)
    return res


@app.get("/get_processed_datetime")
async def get_processed_datetime(date: str, time: str, gym: str) -> dict | None:
    if time != str(validate_time(str_to_time(time), str_to_date(date).weekday()))[:5]:
        return None
    with open("processed_data.json") as file:
        processed_load = json.load(file)[gym]["load"]
    return processed_load[date][time]


@app.get("/get_daily_list")
async def get_daily_list(date: str, time: str, gym: str) -> dict | None:
    # if time != str(validate_time(str_to_time(time), str_to_date(date).weekday()))[:5]:
    #     return None
    with open("processed_data.json") as file:
        processed = json.load(file)[gym]["load"][date]
    items = sorted(filter(lambda item: item[0] <= time, processed.items()))
    x = list(range(len(items)))
    y = [obj[1]["visitors_num"] for obj in items]
    return {"time": x, "data": y}
