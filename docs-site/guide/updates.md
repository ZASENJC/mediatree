# 升级与回滚

MediaTree 有两类更新路径：应用包更新和完整 Docker 镜像更新。两者共用版本基线，但适用场景不同。

## 应用包更新

大多数功能更新属于应用包更新。设置页会从 GitHub Release 下载 `mediatree-app-<version>.tar.gz`，解压到 `./data/releases` 并在重启后生效。

应用包更新的特点：

- 不需要挂载 Docker socket。
- 更新包存放在数据卷中。
- 成功重启后保留当前版本和一个上一版本。
- 失败或不满意时可在设置页回滚。

## 完整镜像更新

当版本涉及运行环境时，需要完整 Docker 镜像更新，例如：

- Python 版本或依赖层变化。
- ffmpeg、字体、系统包变化。
- 容器用户、权限、入口脚本或启动流程变化。
- 任何无法只替换应用代码安全交付的变更。

推荐在宿主机执行：

```bash
docker compose pull
docker compose up -d
```

如果确认要让设置页执行完整镜像更新，需要挂载 Docker socket，并使用包含 Docker CLI 的镜像：

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

该挂载会让容器获得宿主机 Docker 控制权。不确定时不要挂载。

## 新安装用户

维护者发布应用包更新时，也会在本地刷新 `zasenjc/mediatree:latest`。因此新安装用户使用 `latest` 镜像时会直接获得最新应用基线。

## 回滚

应用包更新支持回滚到上一应用版本或镜像内置版本。完整镜像更新的回滚需要由宿主机 Docker 或镜像标签管理。
