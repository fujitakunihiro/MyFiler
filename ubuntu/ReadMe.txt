■起動
　docker run -it ubuntu
 

■セットアップ
docker pull ubuntu:latest
docker run -it ubuntu
④ 初期セットアップ（必要に応じて）

Ubuntuのパッケージを更新：

apt update
apt upgrade -y


エディタやツールを入れる：

apt install -y vim curl git

exit