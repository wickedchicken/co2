import argparse
from datetime import datetime, timezone

import pandas

from plotly.subplots import make_subplots
import plotly.graph_objects as go

from playhouse.mysql_ext import MariaDBConnectorDatabase

from co2 import get_config_data, get_db_connection_data, db_proxy, LogEntry

BEGIN_DATE = datetime(2024, 1, 1, 00, 00, tzinfo=timezone.utc)
END_DATE = datetime.now(timezone.utc)
# end = datetime(2023, 7, 27, 00, 00, tzinfo=timezone.utc)

def get_args():
    parser = argparse.ArgumentParser()
    return parser.parse_args()


def plot(x, y):
    fig = px.bar(x=x, y=y)
    fig.write_html('data.html', auto_open=True)

def get_data(args):
    return LogEntry.select().where(LogEntry.recorded.between(BEGIN_DATE, END_DATE)).where(LogEntry.measurement_type == 'sensor_recording').order_by(LogEntry.recorded)

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
        data = data_frame_from_peewee_query(get_data(args))
        meteoblue_data = data_frame_from_peewee_query(get_meteoblue_data(args))
        fig = make_subplots(rows=2, cols=1, x_title="All times in UTC")
        fig.add_trace(
            go.Scatter(
            x=data["recorded"], y=data["temperature_c"],
            name="recorded temperature",
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
        fig.add_trace(
            go.Scatter(
            x=data["recorded"], y=data["co2_ppm"],
            name="recorded co2",
            ),
            row=2, col=1
        )
        fig.show()
    finally:
        db.close()

if __name__ == '__main__':
    main()