import inject
import pytimeparse
import pandas as pd

from typing import Optional, List
from functools import partial
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId

from config import settings

from loguru import logger


def mongo_period_filter_request(period: str, 
                                end_timestamp: Optional[float],
                                field: str='_id', 
                                use_objectid: bool=False):
    period_seconds = pytimeparse.parse(period)

    if end_timestamp is None:
        end = datetime.utcnow()
    else:
        end = datetime.fromtimestamp(end_timestamp)
    start = end - timedelta(seconds=period_seconds)

    if use_objectid:
        end = ObjectId.from_datetime(end)
        start = ObjectId.from_datetime(start)

    if end_timestamp is None:
        request = {field: {"$gt": start}}
    else:
        request = {field: {"$gt": start, "$lt": end}}
    logger.info(f'Reading stats with request: {request}')
    return request


@inject.autoparams()
def _read_requests(period: str, 
                   end_timestamp: Optional[float]=None, 
                   client: Optional[MongoClient]=None):    
    req = mongo_period_filter_request(period, end_timestamp, field='timestamp', use_objectid=False)
    data = client.pyton.request_stats.find(req)
    data = list(data)
    data = pd.DataFrame(data)
    if '_id' in data:
        data.drop(columns='_id', inplace=True)
    return data


@inject.autoparams()
def _read_liteserver_tasks(period: str, 
                           end_timestamp: Optional[float]=None,
                           client: Optional[MongoClient]=None):    
    req = mongo_period_filter_request(period, end_timestamp, field='timestamp', use_objectid=False)
    data = client.pyton.liteserver_tasks.find(req)
    data = list(data)
    for x in data:
        ls_info = x.pop('liteserver_info')
        x['liteserver'] = '{number}:{ip}:{port}'.format(**ls_info)
        x['archival_liteserver'] = ls_info['archival']
        if x['result_type'] != 'error' and x['result_type'] != 'unknown':
            x['status'] = 'ok'
        else:
            x['status'] = 'error'
    data = pd.DataFrame(data)
    if '_id' in data:
        data.drop(columns='_id', inplace=True)
    return data


def _compute_stats(data, index: List[str]):
    if len(index) == 0:
        index.append('unit')
        
    data = data.copy()
    data['unit'] = 1
    data['count'] = 1
    
    q95 = partial(pd.Series.quantile, q=0.95)
    q99 = partial(pd.Series.quantile, q=0.99)
    
    stats = data.groupby(index).agg({'elapsed': ['mean', q95, q99, 'max'], 'count': 'sum'})
    stats.columns = ['response_time(mean)',
                     'response_time(quantile=0.95)', 
                     'response_time(quantile=0.99)', 
                     'response_time(max)', 
                     'count']
    stats = stats.reset_index()
    if 'unit' in stats:
        stats.drop(columns='unit', inplace=True)
    return stats
