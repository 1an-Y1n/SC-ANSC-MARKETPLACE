#!/bin/sh
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

#set -x
# ========== 全局路径，全部统一放到用户home，跨项目共享 ==========
PJ_FOLDER_FILE=~/.gitnexus/working_project
GLOBAL_GITNEXUS_HOME=~/.gitnexus
# 【修改】lbdb / cache 放在 ~/.gitnexus 内部
GLOBAL_CACHE="${GLOBAL_GITNEXUS_HOME}/.cache"
GLOBAL_LBDB="${GLOBAL_GITNEXUS_HOME}/.lbdb"
# 全局注册表（GitNexus 写在容器内 /data/gitnexus/registry.json）：必须挂载出来，
# 否则容器每次重建都会丢，MCP 与 `gitnexus list` 会报 "No indexed repositories"
GLOBAL_DATA="${GLOBAL_GITNEXUS_HOME}/data"
#DOCKER_IMG=ghcr.io/abhigyanpatwari/gitnexus:1.6.12
DOCKER_IMG=ghcr.io/abhigyanpatwari/gitnexus:latest

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取宿主机用户信息
HOST_UID=$(id -u)
HOST_GID=$(id -g)
HOST_USER=$(id -un)
CT_NAME=gitnexus_${HOST_USER}

# ========== 项目清单文件：保存所有要挂载的项目绝对路径 ==========
PROJECT_LIST=${GLOBAL_GITNEXUS_HOME}/project_list.txt

help_msg() {
    echo "GitNexus Docker 多项目管理脚本"
    echo "用法: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "命令:"
    echo "  start              启动容器（加载project_list内全部项目）"
    echo "  add                添加当前目录：登记 → 必要时重建容器挂载 → 建索引（已登记过的只登记不索引）"
    echo "  remove             将当前目录从项目列表移除（下次重启不再挂载）"
    echo "  index              只对【当前目录】执行索引更新（容器未运行时会自动启动）"
    echo "  index-all          批量更新project_list里全部项目索引（供crontab调用）"
    echo "  list               列出所有已注册项目"
    echo "  stop               停止并删除容器"
    echo ""
    echo "参数:"
    echo "  --skip-skills      索引时关闭自动生成skills（默认开启 --skills）"
    echo "  --no-index         只登记并挂载，不建索引（批量登记多个项目时用）"
    echo "  -b,--background    后台模式执行索引（无交互输出）"
    echo "  -h,--help          显示本帮助信息"
    echo ""
    echo "示例："
    echo "  1. 首次启动容器：$0 start"
    echo "  2. 进入项目A目录，加入项目并建索引：$0 add"
    echo "  3. 进入项目B目录，只登记并挂载（不索引）：$0 add --no-index"
    echo "  4. 代码变更后，在项目目录增量更新索引：$0 index"
    echo "  5. 索引时临时不生成skills：$0 index --skip-skills"
    echo "  6. 移除当前项目：$0 remove"
    echo "  7. 查看全部注册项目：$0 list"
    echo "  8. 批量更新所有项目（crontab）：$0 index-all -b"
    exit 0
}

# 加载项目列表，生成docker -v 挂载参数
build_volume_args() {
    VOL_ARGS=""
    while IFS= read -r line; do
        # 跳过空行
        [ -z "$line" ] && continue
        if [ -d "$line" ]; then
            # 身份映射：宿主机路径原样挂载到容器内的同一路径
            VOL_ARGS="${VOL_ARGS} -v ${line}:${line}"
        fi
    done < "${PROJECT_LIST}"
    echo "$VOL_ARGS"
}

# 确保容器在运行；不在则自动启动（机器重启后 cron 的 index-all 可自愈）
ensure_container() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CT_NAME}$"; then
        echo "${YELLOW}ℹ️ GitNexus 容器未运行，自动启动 ...${NC}"
        "$0" start
        if ! docker ps --format '{{.Names}}' | grep -q "^${CT_NAME}$"; then
            echo "${RED}❌ 错误: 自动启动容器失败！请手动执行 $0 start${NC}"
            exit 1
        fi
    fi
}

# 宿主路径在容器内是否可见（身份映射：宿主路径 == 容器路径）。
# 路径没挂载时 docker exec -w 会抛裸 OCI 错误，所以 exec 之前先问一次。
is_mounted() {
    docker exec "${CT_NAME}" test -d "$1" >/dev/null 2>&1
}

# 索引函数，接收：项目绝对路径（身份映射，宿主与容器内一致），background，skip_skills
do_index() {
    local PROJ_PATH="$1"
    local background="$2"
    local skip_skills="$3"

    ensure_container

    # 没挂载就 exec 进去只会得到 OCI 原文，这里提前换成可读提示
    if ! is_mounted "${PROJ_PATH}"; then
        echo "${RED}❌ 项目尚未挂载进容器：${PROJ_PATH}${NC}"
        echo "${YELLOW}   请先执行：$0 stop && $0 start${NC}"
        return 1
    fi

    echo "${YELLOW}🔍 开始索引: ${PROJ_PATH}（大仓库可能需要几分钟到十几分钟，请耐心等待）...${NC}"
    # 有 TTY 才用 -it（前台能看到进度）；无 TTY 时自动退化，否则 docker exec 会挂住
    if [ "$background" -eq 1 ]; then
        EXEC_OPTS=""
    elif [ ! -t 0 ]; then
        echo "${YELLOW}   （无 TTY，改用非交互模式）${NC}"
        EXEC_OPTS=""
    else
        EXEC_OPTS="-it"
    fi

    # ========== 变更：默认开启 --skills，可选参数 --skip-skills 关闭 ==========
    SKILL_ARG="--skills"
    if [ "$skip_skills" -eq 1 ]; then
        SKILL_ARG="--skip-skills"
    fi

    # --skip-agents-md：不注入 AGENTS.md / CLAUDE.md —— 它们是团队共享的跟踪文件，不能被本地索引反复重写
    # 身份映射下宿主路径在容器内同样有效，linked worktree 的 .git 也因此天然可解析
    docker exec $EXEC_OPTS \
        -u ${HOST_UID}:${HOST_GID} \
        -w "${PROJ_PATH}" \
        ${CT_NAME} \
        gitnexus analyze "${PROJ_PATH}" --embeddings ${SKILL_ARG} --max-file-size 32768 --skip-agents-md --verbose
    if [ $? -ne 0 ]; then
        echo "${RED}❌ 索引失败！项目 ${PROJ_PATH} 索引出错${NC}"
        return 1
    fi
    echo ""
    echo "${BLUE}==============================================${NC}"
    echo "${GREEN}🎉 索引完成！${PROJ_PATH}${NC}"
    echo "${BLUE}==============================================${NC}"
    echo ""
    return 0
}

# ====================== 主逻辑 ======================
# 初始化全局目录，包含 .cache .lbdb data
mkdir -p ${GLOBAL_GITNEXUS_HOME}
mkdir -p ${GLOBAL_CACHE}
mkdir -p ${GLOBAL_LBDB}
mkdir -p ${GLOBAL_DATA}
touch ${PROJECT_LIST}

# 变量默认
CMD=""
BACKGROUND=0
SKIP_SKILLS=0
NO_INDEX=0

# 参数解析
TEMP=$(getopt -o bh --long background,skip-skills,no-index,help -n "$0" -- "$@")
if [ $? != 0 ]; then
  help_msg
fi
eval set -- "$TEMP"
while true; do
  case "$1" in
    -b|--background)
      BACKGROUND=1; shift ;;
    --skip-skills)
      SKIP_SKILLS=1; shift ;;
    --no-index)
      NO_INDEX=1; shift ;;
    -h|--help)
      help_msg; shift ;;
    --)
      shift ; break ;;
    *)
      help_msg; break ;;
  esac
done

CMD="$1"
shift

case "${CMD}" in
start)
    echo "${BLUE}📅 当前时间: $(date)${NC}"
    echo "${BLUE}==============================================${NC}"
    echo "${YELLOW}📦 GitNexus Docker 多项目容器启动${NC}"
    echo "${BLUE}==============================================${NC}"
    echo "${GREEN}✅ Host User:${NC} $HOST_USER (UID=$HOST_UID, GID=$HOST_GID)"
    echo ""

    # Clean previous container
    echo "${BLUE}🧹 清理旧容器 ...${NC}"
    docker stop ${CT_NAME} >/dev/null 2>&1 && docker rm ${CT_NAME} >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "${GREEN}✅ 旧容器已清理${NC}"
    else
        echo "${YELLOW}ℹ️ 未找到旧容器，跳过清理${NC}"
    fi
    echo ""

    VOLUME_ARGS=$(build_volume_args)
    echo "${BLUE}🚀 启动新容器: ${YELLOW}${CT_NAME}${NC}"
    echo "${BLUE}📂 已挂载项目列表：${NC}"
    cat ${PROJECT_LIST}
    echo ""

    docker run -d --rm \
        --name ${CT_NAME} \
        -u root \
        -e HOME=/home/${HOST_USER} \
        -e HOST_USER=${HOST_USER} \
        -e HOST_UID=${HOST_UID} \
        -e HOST_GID=${HOST_GID} \
        -e NODE_OPTIONS="--max-old-space-size=16384" \
        -v ${GLOBAL_GITNEXUS_HOME}:/home/${HOST_USER}/.gitnexus \
        -v ${GLOBAL_CACHE}:/home/${HOST_USER}/.cache \
        -v ${GLOBAL_LBDB}:/home/${HOST_USER}/.lbdb \
        -v ${GLOBAL_DATA}:/data/gitnexus \
        ${VOLUME_ARGS} \
        ${DOCKER_IMG} \
        tail -f /dev/null
    if [ $? -ne 0 ]; then
        echo "${RED}❌ 容器启动失败！请检查 Docker 环境和权限设置。${NC}"
        exit 1
    fi
    echo "${GREEN}✅ 容器启动成功！${NC}"
    echo ""

    # 初始化容器内用户和权限
    echo "${BLUE}⚙️  初始化容器内用户与权限 ...${NC}"
    docker exec ${CT_NAME} bash -c "
      groupadd -g \${HOST_GID} \${HOST_USER} 2>/dev/null || groupmod -g \${HOST_GID} \${HOST_USER} 2>/dev/null || true
      useradd -u \${HOST_UID} -g \${HOST_GID} -m -s /bin/bash \${HOST_USER} 2>/dev/null || usermod -u \${HOST_UID} -g \${HOST_GID} \${HOST_USER} 2>/dev/null || true
      mkdir -p /home/\${HOST_USER}/.gitnexus /home/\${HOST_USER}/.cache /home/\${HOST_USER}/.lbdb /data/gitnexus
      chown -R \${HOST_UID}:\${HOST_GID} /home/\${HOST_USER}/.gitnexus /home/\${HOST_USER}/.cache /home/\${HOST_USER}/.lbdb /data/gitnexus
      which gitnexus
    "
    if [ $? -ne 0 ]; then
      echo "${RED}❌ 用户权限初始化失败！请检查容器日志。${NC}"
      exit 1
    fi
    echo "${GREEN}✅ 权限与用户初始化完成${NC}"
    echo ""

    echo "${YELLOW}📌 启动 MCP 给 Windsurf 使用：${NC}"
    echo "  docker exec -it -u ${HOST_UID}:${HOST_GID} -w / ${CT_NAME} gitnexus mcp"
    echo ""
    echo "${YELLOW}📌 进入容器命令行：${NC}"
    echo "  docker exec -it -u ${HOST_UID}:${HOST_GID} -w / ${CT_NAME} bash"
    echo ""
    echo "${YELLOW}📌 添加新项目：进入项目目录执行 $0 add${NC}"
    echo "${YELLOW}📌 更新索引：进入项目目录执行 $0 index${NC}"
    echo "${YELLOW}📌 批量更新全部项目：$0 index-all -b${NC}"
    ;;

add)
    # 添加当前目录：登记 → 必要时重建容器挂载 → 建索引
    if [ ! -e ".git" ]; then
        echo "${RED}❌ 错误: 当前目录不是 git 仓库！${NC}"
        echo "${RED}请在你的项目根目录执行此脚本。${NC}"
        exit 1
    fi
    CURR=$(pwd)

    # 本次 add 之前是否已登记。只有「已登记过的重跑」才跳过索引；
    # 新登记的项目（含位于已挂载项目之下的 subdir）照常建索引。
    ALREADY_REGISTERED=0
    grep -xFq "${CURR}" ${PROJECT_LIST} && ALREADY_REGISTERED=1

    echo "${YELLOW}ℹ️ 接下来：登记该项目 → 必要时重建容器把它挂进去（会短暂中断当前 MCP 会话，${NC}"
    echo "${YELLOW}   若助手侧连不上 gitnexus，请重启 Devin Desktop）→ 首次登记时建索引。${NC}"
    echo ""

    # 去重写入
    grep -xFq "${CURR}" ${PROJECT_LIST} || echo "${CURR}" >> ${PROJECT_LIST}
    echo "${GREEN}✅ 已添加项目路径：${CURR}${NC}"

    # 容器没跑就先启动：它读的是刚写好的清单，新项目当场挂上，不必重建
    ensure_container

    if is_mounted "${CURR}"; then
        echo "${GREEN}✅ 该项目已挂载在容器中${NC}"
    else
        echo "${YELLOW}📦 该项目尚未挂载，重建容器以挂载 ...${NC}"
        "$0" start
        if ! is_mounted "${CURR}"; then
            echo "${RED}❌ 重建容器后仍未挂载：${CURR}${NC}"
            echo "${RED}   请检查 $0 list 与容器日志。${NC}"
            exit 1
        fi
    fi

    if [ "${ALREADY_REGISTERED}" -eq 1 ]; then
        echo "${GREEN}✅ 项目此前已登记，跳过索引${NC}"
        echo "${YELLOW}   如需刷新索引：cd ${CURR} && $0 index${NC}"
        exit 0
    fi

    if [ "${NO_INDEX}" -eq 1 ]; then
        echo "${GREEN}✅ 已登记并挂载（--no-index：跳过索引）${NC}"
        echo "${YELLOW}   需要时跑：cd ${CURR} && $0 index${NC}"
        exit 0
    fi

    if ! do_index "${CURR}" ${BACKGROUND} ${SKIP_SKILLS}; then
        echo "${RED}❌ 项目已登记并挂载成功，但索引失败。${NC}"
        echo "${YELLOW}   修好后重试：cd ${CURR} && $0 index${NC}"
        exit 1
    fi
    ;;

remove)
    # 将当前目录从project_list移除
    CURR=$(pwd)
    if [ ! -e ".git" ]; then
        echo "${RED}❌ 警告：当前目录不是git仓库，仍然尝试从列表移除路径${NC}"
    fi
    echo "${YELLOW}🗑️ 准备从项目列表移除：${CURR}${NC}"
    # 使用sed删除完全匹配行，生成新文件
    sed "\|^${CURR}$|d" ${PROJECT_LIST} > ${PROJECT_LIST}.tmp && mv ${PROJECT_LIST}.tmp ${PROJECT_LIST}
    echo "${GREEN}✅ 已移除项目。下次容器重启后不再挂载此目录${NC}"
    echo "${YELLOW}💡 提示：此操作不会删除本地代码、不会删除GitNexus索引数据库，只是不再挂载。如需清除该项目的图谱，需要手动在容器内执行gitnexus remove-repo"
    ;;

index)
    if [ ! -e ".git" ]; then
        echo "${RED}❌ 错误: 当前目录不是 git 仓库！${NC}"
        exit 1
    fi
    CURR=$(pwd)
    do_index "${CURR}" ${BACKGROUND} ${SKIP_SKILLS}
    ;;

# ================= 新增 index-all，给crontab批量更新所有项目 =================
index-all)
    echo "${BLUE}⏳ 批量开始更新全部已登记项目索引${NC}"
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        # 跳过不存在目录
        if [ ! -d "$line" ]; then
            echo "${YELLOW}⚠️ 目录不存在，跳过：${line}${NC}"
            continue
        fi
        echo "${BLUE}===== 处理项目：${line} =====${NC}"
        do_index "${line}" 1 ${SKIP_SKILLS}
    done < "${PROJECT_LIST}"
    echo "${GREEN}✅ index-all 全部任务执行完毕${NC}"
    ;;

list)
    echo "${BLUE}===== 已注册项目列表 =====${NC}"
    cat ${PROJECT_LIST}
    echo "${BLUE}=========================${NC}"
    ;;

stop)
    echo "${BLUE}🛑 停止容器 ${CT_NAME}${NC}"
    docker stop ${CT_NAME}
    ;;

*)
    help_msg
    ;;
esac
