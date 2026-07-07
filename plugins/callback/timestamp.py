# Copyright (c) VAST Data
# SPDX-License-Identifier: Apache-2.0
"""Stdout callback: default output plus a wall-clock timestamp per task."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
    name: timestamp
    type: stdout
    short_description: Default output with a wall-clock timestamp and elapsed time per task
    version_added: "1.0.0"
    description:
        - Drop-in replacement for the C(default) stdout callback that prints a line
          before each task with the current wall-clock time, the duration of the
          previous task, and the cumulative play runtime.
        - Used by C(ansible-test integration) because it force-enables only the
          C(junit) aggregate callback via C(ANSIBLE_CALLBACKS_ENABLED), which would
          override an aggregate timing callback; the stdout callback is not overridden.
    extends_documentation_fragment:
        - default_callback
    requirements:
        - set as stdout in configuration
"""

import time
from datetime import datetime

from ansible.plugins.callback.default import CallbackModule as DefaultCallback


class CallbackModule(DefaultCallback):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "vastdata.vms.timestamp"

    def __init__(self):
        super().__init__()
        # Started once per ansible-playbook process and never reset, so `total`
        # accumulates across all plays in the run (e.g. multi-play role tests)
        # instead of restarting at each play.
        self._run_start = time.time()
        self._last = self._run_start

    def _stamp(self, label):
        now = time.time()
        wall = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._display.display(
            "%s | task=%6.2fs | total=%7.2fs | %s" % (wall, now - self._last, now - self._run_start, label),
            color="bright purple",
        )
        self._last = now

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._stamp(task.get_name().strip())
        super().v2_playbook_on_task_start(task, is_conditional)

    def v2_playbook_on_handler_task_start(self, task):
        self._stamp("HANDLER: " + task.get_name().strip())
        super().v2_playbook_on_handler_task_start(task)
