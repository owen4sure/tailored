#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""擲骰選方向。

為什麼要交給亂數：讓 AI 自己挑，它幾乎一定挑統計上最安全的那個。
抽中的方向必須被認真發展成主提案，不能一句「太大膽」就略過。

用法：
  python roll.py 火警總機 夜班觀察紀錄 燈塔守夜日誌 [--seed 42] [--log design-review/roll.json]
"""
import argparse
import json
import os
import random
import time


def roll(candidates, seed=None):
    if len(candidates) < 2:
        raise ValueError("至少要兩個候選方向才有得擲。")
    if seed is None:
        seed = random.SystemRandom().randrange(1, 10 ** 9)
    rng = random.Random(seed)
    return rng.choice(candidates), seed


def main():
    ap = argparse.ArgumentParser(description="擲骰選設計方向")
    ap.add_argument("candidates", nargs="+")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--log")
    a = ap.parse_args()
    chosen, seed = roll(a.candidates, a.seed)
    print("候選：" + "、".join(a.candidates))
    print("抽中：" + chosen + "（seed=" + str(seed) + "）")
    if a.log:
        os.makedirs(os.path.dirname(os.path.abspath(a.log)), exist_ok=True)
        with open(a.log, "w", encoding="utf-8") as f:
            json.dump({"candidates": a.candidates, "chosen": chosen, "seed": seed,
                       "time": time.strftime("%Y-%m-%dT%H:%M:%S")}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
