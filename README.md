# Physical AI：日本語の自然言語指示によるロボット制御

## 概要

日本語で指示すると、Geminiが前進・旋回・停止の行動列をJSONとして生成し、ROS 2を通してGazebo上の差動二輪ロボットが動作するデモです。追加学習は行わず、既存の生成AIを推論に利用します。

**処理構成**

    日本語の指示
       ↓
    Gemini 3.5 Flash-Lite（動作列の生成）
       ↓
    Python（JSON形式・動作種類・秒数の検証、実行前の確認）
       ↓
    ROS 2 /cmd_vel → ros_ign_bridge
       ↓
    Ignition Gazebo / demoRobot（前進・旋回・停止）

### 実演した指示

> 2秒前進して、左に2秒その場で旋回して、さらに2秒前進して止まって

Geminiが生成した行動列：

    [
      {"action": "forward", "seconds": 2.0},
      {"action": "left", "seconds": 2.0},
      {"action": "forward", "seconds": 2.0},
      {"action": "stop", "seconds": 0.2}
    ]

**実験結果（1回のGazebo実演）**

| 項目 | 開始前 | 実行後 |
| --- | ---: | ---: |
| X座標 | 0.0000 m | 0.4736 m |
| Y座標 | 0.0000 m | 0.2746 m |
| Yaw（方向） | 0.0000 rad | 0.9788 rad |

実行結果はシミュレーション速度などに依存し、厳密な位置制御や指定角度の保証を意味しません。

## 独自の工夫

- 日本語の自然言語指示をGeminiで複数ステップの行動計画に変換
- AIの出力を最大6ステップ・5種類の行動・各0.2～3.0秒に限定し、不正な動作列は拒否
- 人による実行承認を挟んでからROS 2に速度指令を送信
- 各ステップ間と終了時に停止指令を送信し、移動し続けることを防ぐ
- AIによる計画と決定論的なロボット動作指令を分離

本作品は自然言語の行動計画デモであり、映像認識・障害物回避・自己位置推定・閉ループ位置制御は実装していません。実機での安全性は保証しません。

## 実行環境

- Windows 11、Docker Desktop
- ROS 2 Humble（Ubuntuベースのコンテナ）
- Ignition Gazebo / ros_ign_bridge
- Python 3、rclpy
- Gemini API（実演時：gemini-3.5-flash-lite）

利用したDockerイメージ：

    airobotbook/ros2-desktop-ai-robot-book-humble:latest

## 再現方法

### 1. Dockerを起動（Windows PowerShell）

    New-Item -ItemType Directory -Force -Path C:\pai-final
    docker pull airobotbook/ros2-desktop-ai-robot-book-humble:latest
    docker run -d --name pai-final -p 127.0.0.1:6081:80 --shm-size=1g -e RESOLUTION=1280x800 -e LIBGL_ALWAYS_SOFTWARE=1 -v "C:\pai-final:/home/ubuntu/work" airobotbook/ros2-desktop-ai-robot-book-humble:latest

ブラウザで http://localhost:6081 を開きます。すでに同名コンテナがあれば新規作成せず再利用してください。

このリポジトリの ai_drive.py を Windows の C:\pai-final にコピーします。

### 2. ロボットの世界データを取得（Ubuntuターミナル）

    cd /home/ubuntu/work
    git clone https://github.com/OsawaKousei/2DRoboPrac_ws.git source

モデルの元リポジトリは別途ダウンロードして使用します。本リポジトリにはモデル・メッシュの複製を含めていません。

### 3. Gazebo起動（UbuntuターミナルA）

    export IGN_GAZEBO_RESOURCE_PATH=/home/ubuntu/work/source/ros2_ws/src/nav_dev/models
    ign gazebo -r -v 3 /home/ubuntu/work/source/ros2_ws/src/nav_dev/models/world.sdf --render-engine ogre2

GazeboのEntity Treeから demoRobot を選び、PoseのX・Y・Yawで位置と向きを確認できます。

### 4. ROS 2ブリッジ起動（UbuntuターミナルB）

    source /opt/ros/humble/setup.bash
    ros2 run ros_ign_bridge parameter_bridge '/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist'

### 5. Gemini APIのキーを設定して実行（Windows PowerShell）

Google AI Studioで発行したAPIキーをクリップボードにコピーします。キーをGitHub、ソースコード、画面録画に含めないでください。

    $k = (Get-Clipboard -Raw).Trim()
    docker exec -it -e "GEMINI_API_KEY=$k" -e "GEMINI_MODEL=gemini-3.5-flash-lite" pai-final bash -lc 'source /opt/ros/humble/setup.bash && python3 /home/ubuntu/work/ai_drive.py'

日本語で動作を指示し、AIが生成したJSONを確認して y を入力すると実行します。

モデルは利用可能なものへ切り替えられます（GEMINI_MODEL環境変数）。利用料金・無料枠・提供モデルはGoogle側の条件によります。

### 6. 動かない場合

- Gazeboが一時停止していないことを確認します。
- Gazebo右下のReal Time Factorが極端に低い場合は、Gazeboを再起動します。
- ROS 2ブリッジの購読者を確認します。

      source /opt/ros/humble/setup.bash
      ros2 topic info /cmd_vel

- Gemini APIのエラーがある場合、APIキーの有効性・利用可能なモデル・料金設定を確認します。

## 外部資料・ライセンスの表示

ロボットモデルとGazebo/ROS 2の基本構成は以下を参照しています。**独自に追加したのは、Geminiによる日本語の動作計画とROS 2への安全な指令送信を行う ai_drive.py です。**

- [ROS2とGazeboの連携によるロボット操作（解説記事）](https://qiita.com/N622/items/9d89f77d85d9da0af29e)
- [OsawaKousei / 2DRoboPrac_ws](https://github.com/OsawaKousei/2DRoboPrac_ws)（元モデル・Apache License 2.0）
- [AI-Robot-Book-Humble / docker-ros2-desktop-ai-robot-book-humble](https://github.com/AI-Robot-Book-Humble/docker-ros2-desktop-ai-robot-book-humble)

本リポジトリにAPIキー、個人情報、撮影動画、元モデルの大容量データは含めていません。
