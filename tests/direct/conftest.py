"""Shared real GenVM Direct Mode fixtures for Quorum Clean."""

import atexit
import os
import sys

import pytest


_real_unlink = os.unlink
_deferred = []


def _safe_unlink(path, *args, **kwargs):
    try:
        return _real_unlink(path, *args, **kwargs)
    except PermissionError:
        _deferred.append(path)


os.unlink = _safe_unlink


@atexit.register
def _cleanup():
    for path in _deferred:
        try:
            _real_unlink(path)
        except OSError:
            pass


@pytest.fixture
def contract(direct_deploy):
    return direct_deploy("contracts/QuorumClean.py")


def set_block_time(direct_vm, iso="2026-01-15T12:00:00Z"):
    direct_vm.warp(iso)
    gl = sys.modules.get("genlayer.gl")
    if gl is not None and getattr(gl, "message_raw", None) is not None:
        gl.message_raw["datetime"] = iso
    return iso


class ValueLedger:
    def __init__(self, vm):
        self.vm = vm
        self.funded = 0
        self.transfers = []

    def fund(self, amount):
        self.vm.value = int(amount)
        self.funded += int(amount)
        return int(amount)

    def no_value(self):
        self.vm.value = 0

    def _hook(self, _vm, request):
        send = request.get("EthSend") if isinstance(request, dict) else None
        if send is not None:
            self.transfers.append((send.get("address"), int(send["value"])))
            return {"ok": None}
        return None

    @property
    def paid_out(self):
        return sum(value for _, value in self.transfers)

    @property
    def retained(self):
        return self.funded - self.paid_out


@pytest.fixture
def value_ledger(direct_vm):
    ledger = ValueLedger(direct_vm)
    direct_vm._gl_call_hook = ledger._hook
    return ledger
