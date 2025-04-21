{pkgs}: {
  deps = [
    pkgs.redis
    pkgs.ffmpeg
    pkgs.ffmpeg-full
    pkgs.postgresql
    pkgs.openssl
  ];
}
