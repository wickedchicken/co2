import argparse
from datetime import datetime, timedelta, timezone

import pandas

from plotly.subplots import make_subplots
import plotly.graph_objects as go

from playhouse.mysql_ext import MariaDBConnectorDatabase

from co2 import get_config_data, get_db_connection_data, db_proxy, LogEntry

#BEGIN_DATE = datetime(2024, 5, 1, 00, 00, tzinfo=timezone.utc)
END_DATE = datetime.now(timezone.utc)
BEGIN_DATE = None
#END_DATE - timedelta(days=30)
# end = datetime(2023, 7, 27, 00, 00, tzinfo=timezone.utc)

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days-back', type=int, default=30)
    return parser.parse_args()


def plot(x, y):
    fig = px.bar(x=x, y=y)
    fig.write_html('data.html', auto_open=True)


def get_room_names(args):
    data = LogEntry.select(LogEntry.room_name).distinct().where(LogEntry.recorded.between(BEGIN_DATE, END_DATE)).where(LogEntry.measurement_type << ('sensor_recording', 'usbtemp')).execute()
    return [x.room_name for x in data]

def get_data(args, room_name):
    return LogEntry.select().where(LogEntry.recorded.between(BEGIN_DATE, END_DATE)).where(LogEntry.measurement_type << ('sensor_recording', 'usbtemp')).where(LogEntry.room_name == room_name).order_by(LogEntry.recorded)

def get_meteoblue_data(args):
    return LogEntry.select().where(LogEntry.recorded.between(BEGIN_DATE, END_DATE)).where(LogEntry.measurement_type == 'meteoblue').order_by(LogEntry.recorded)

def data_frame_from_peewee_query(query):
    connection = query._database.connection()
    sql, params = query.sql()
    return pandas.read_sql_query(sql, connection, params=params)

def main():
    config_data = get_config_data()
    db_login, db_password = get_db_connection_data(config_data)

    args = get_args()

    global BEGIN_DATE


    BEGIN_DATE = END_DATE - timedelta(days=args.days_back)


    db = MariaDBConnectorDatabase(
        config_data['database']['name'],
        host=config_data['database']['hostname'],
        port=int(config_data['database']['port']),
        user=db_login,
        password=db_password,
    )
    db_proxy.initialize(db)
    db.connect()
    try:
        data = {}
        room_names = get_room_names(args)
        print(room_names)
        for room in room_names:
            data[room] = data_frame_from_peewee_query(get_data(args, room))

        meteoblue_data = data_frame_from_peewee_query(get_meteoblue_data(args))
        fig = make_subplots(rows=2, cols=1, x_title="All times in UTC")
        for room, room_data in data.items():
            if any(room_data["temperature_c"]):
                fig.add_trace(
                    go.Scatter(
                    x=room_data["recorded"], y=room_data["temperature_c"],
                    name=f"{room} temperature",
                    ),
                    row=1, col=1
                )
        fig.add_trace(
            go.Scatter(
            x=meteoblue_data["recorded"], y=meteoblue_data["temperature_c"],
            name="meteoblue temperature",
            ),
            row=1, col=1
        )
        for room, room_data in data.items():
            if any(room_data["co2_ppm"]):
                fig.add_trace(
                    go.Scatter(
                    x=room_data["recorded"], y=room_data["co2_ppm"],
                    name=f"{room} co2",
                    ),
                    row=2, col=1
                )
        fig.show()
    finally:
        db.close()

if __name__ == '__main__':
    main()