"""Compatibility adapter; explicit simulation by default, HTTPS only for bench access."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pharm.hardware import HttpHardware, Simulator, Result, compartment

_client = None
def configure(client):
    global _client
    _client = client

def client():
    global _client
    if _client is None:
        _client = Simulator()
    return _client

def open_drawer(drawer_num):
    return client().open(drawer_num)

def lock_drawer(drawer_num=None):
    if drawer_num is not None:
        compartment(drawer_num)
    return client().lock()

def emergency_unlock():
    return Result(False, "Emergency all-compartment unlock is disabled pending hardware requirements.")

def control_light(box_num):
    compartment(box_num)
    if isinstance(client(), HttpHardware):
        return client().request("/light", {"box": box_num})
    return Result(True, "Simulated light command. No hardware moved.")

def unlock_cabinet_lock(box_num):
    return open_drawer(box_num)

def lock_cabinet_lock(box_num):
    compartment(box_num)
    if isinstance(client(), HttpHardware):
        return client().request("/lock_cabinet_lock", {"box": box_num})
    return client().lock()

def check_api_status():
    return client().status()
