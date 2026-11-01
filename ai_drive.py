#!/usr/bin/env python3
"""Japanese natural-language commands to a simulated ROS 2 differential-drive robot.

AI inference uses Gemini generateContent. Without a valid response, do not move.
Only the fixed action vocabulary, duration, and velocity limits can reach cmd_vel.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
TOPIC = os.getenv("ROS_CMD_VEL_TOPIC", "/cmd_vel")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
ALLOWED = {"forward", "backward", "left", "right", "stop"}
MAX_STEPS = 6
MAX_DURATION = 3.0
SPEED = 0.20  # meters per second
TURN = 0.60   # radians per second
PERIOD = 0.1  # 10 Hz


def ask_ai(instruction: str):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("GEMINI_API_KEY is not set")
    prompt = (
        "あなたは差動二輪ロボットの安全な動作プランナーです。"
        "次の日本語指示をJSON配列の動作列に変換してください。"
        '各要素は {"action": "forward|backward|left|right|stop", "seconds": 数値} のみ。'
        "最大6動作、各動作の秒数は0.2以上3.0以下。"
        "左・右はその場旋回、前進・後退は直進。"
        "達成不可能・曖昧・危険な指示は空配列 [] にしてください。"
        "ロボットにはカメラや測位装置が無いので、見えない物体や地点への自律誘導は禁止。"
        "移動速度や角度は出力しないこと。"
        f"指示：{instruction}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini HTTP {exc.code}: check API key/model/quota") from exc
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        plan = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("AI returned invalid JSON") from exc
    validate_plan(plan)
    return plan


def validate_plan(plan):
    if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_STEPS:
        raise ValueError("AI plan must contain 1-6 steps (empty plan rejected)")
    for step in plan:
        if not isinstance(step, dict) or set(step) != {"action", "seconds"}:
            raise ValueError(f"Unexpected step fields: {step!r}")
        action, seconds = step["action"], step["seconds"]
        if action not in ALLOWED:
            raise ValueError(f"Unsupported action: {action!r}")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise ValueError("Duration must be numeric")
        if not 0.2 <= seconds <= MAX_DURATION:
            raise ValueError("Duration outside safe bounds")


def command(action):
    msg = Twist()
    if action == "forward":
        msg.linear.x = SPEED
    elif action == "backward":
        msg.linear.x = -SPEED
    elif action == "left":
        msg.angular.z = TURN
    elif action == "right":
        msg.angular.z = -TURN
    return msg


def send_for(node, pub, msg, seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0)
        time.sleep(PERIOD)


def main():
    instruction = " ".join(sys.argv[1:]).strip()
    if not instruction:
        instruction = input("ロボットへの日本語指示: ").strip()
    if not instruction:
        raise ValueError("Instruction is empty")
    # Inference takes place before motion; failed requests cannot move robot.
    plan = ask_ai(instruction)
    print("AIが生成した動作列:", json.dumps(plan, ensure_ascii=False))
    answer = input("この動作列を実行しますか？ [y/N]: ").strip().lower()
    if answer != "y":
        print("キャンセルしました")
        return
    rclpy.init()
    node = Node("pai_ai_drive")
    pub = node.create_publisher(Twist, TOPIC, 10)
    stop = Twist()
    try:
        time.sleep(2.0)  # Allow DDS subscribers to discover this publisher.
        for step in plan:
            print("実行:", step)
            send_for(node, pub, command(step["action"]), step["seconds"])
            send_for(node, pub, stop, 0.3)
    finally:
        send_for(node, pub, stop, 1.0)
        node.destroy_node()
        rclpy.shutdown()
    print("完了。停止指令を送信しました。")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, urllib.error.URLError) as exc:
        print("実行中止:", exc, file=sys.stderr)
        sys.exit(1)
