#!/usr/bin/env python3
# Copyright (c) 2026 SerComm Corporation. All Rights Reserved.
#
# SerComm Corporation reserves the right to make changes to this document
# without notice. SerComm Corporation makes no warranty, representation or
# guarantee regarding the suitability of its products for any particular
# purpose.
#
# SerComm Corporation assumes no liability arising out of the application or
# use of any product or circuit.
#
# SerComm Corporation specifically disclaims any and all liability, including
# without limitation consequential or incidental damages; neither does it convey
# any license under its patent rights, nor the rights of others.

"""Post a question from the running Devin session to the JIRA ticket.

Called by the agent when it needs human input (see prompts/task_prompt.md).
The comment is prefixed with config.comment_prefix so the poller can tell bot
comments apart from human ones, and JiraClient.add_comment adds a self-mention so
the human actually gets a notification.

Usage:
    ask_human.py <TICKET> <question text...>
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
from jira_client import JiraClient


def main():
    if len(sys.argv) < 3:
        print("usage: ask_human.py <TICKET> <question text...>")
        return 2
    ticket = sys.argv[1]
    question = " ".join(sys.argv[2:])

    cfg = common.load_config()
    jira = JiraClient(common.load_jira_config(cfg))
    body = "{}\n\n{}".format(cfg["comment_prefix"], question)
    c = jira.add_comment(ticket, body)
    print("posted comment {} to {}".format(c.get("id"), ticket))
    return 0


if __name__ == "__main__":
    sys.exit(main())
