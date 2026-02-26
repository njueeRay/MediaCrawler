# 代理 IP 使用指南

> 再次提醒：不要对自媒体平台进行大规模爬取或其他违法行为，请遵守相关法律法规和平台服务条款。

## 代理方案对比

| 方案 | 适用用户 | 费用 | 接入难度 | 说明 |
|------|---------|------|---------|------|
| [快代理](#快代理) | 个人 / 企业 | 付费（有试用） | ⭐⭐ | 需要 4 个参数（secret_id / signature / user_name / pwd） |
| [豌豆HTTP](#豌豆http) | 企业用户 | 付费（有试用） | ⭐ | 只需 1 个参数（app_key） |

## 整体流程

![代理 IP 使用流程图](../static/images/代理IP%20流程图.drawio.png)

代理 IP 通过 `.env` 配置写入，爬虫启动时自动从 `proxy/proxy_ip_pool.py` 读取。

---

## 快代理

> 支持个人和企业用户。

### 准备代理 IP 信息

点击 <a href="https://www.kuaidaili.com/?ref=ldwkjqipvz6c">快代理</a> 官网注册并实名认证（国内使用代理 IP 必须实名）。

### 获取密钥信息

从官网获取免费试用：

![快代理试用页面](../static/images/img.png)

注意选择**私密代理**：

![选择私密代理](../static/images/img_1.png)

开通试用：

![开通试用](../static/images/img_2.png)

### 配置代码

需要 4 个参数（在试用订单中可以查看）：

```python
# 文件地址： proxy/providers/kuai_daili_proxy.py
def new_kuai_daili_proxy() -> KuaiDaiLiProxy:
    return KuaiDaiLiProxy(
        kdl_secret_id=os.getenv("kdl_secret_id", "你的快代理 secret_id"),
        kdl_signature=os.getenv("kdl_signature", "你的快代理签名"),
        kdl_user_name=os.getenv("kdl_user_name", "你的快代理用户名"),
        kdl_user_pwd=os.getenv("kdl_user_pwd", "你的快代理密码"),
    )
```

参数查看位置：

- `kdl_user_name`、`kdl_user_pwd`

  ![用户名和密码](../static/images/img_3.png)

- `kdl_secret_id`、`kdl_signature`

  ![secret_id 和签名](../static/images/img_4.png)

### .env 配置

```bash
kdl_secret_id=你的快代理secret_id
kdl_signature=你的快代理签名
kdl_user_name=你的快代理用户名
kdl_user_pwd=你的快代理密码
```

---

## 豌豆HTTP

> 仅支持企业用户。

### 准备代理 IP 信息

点击 <a href="https://h.wandouip.com?invite_code=rtnifi">豌豆HTTP代理</a> 官网注册并实名认证。

### 获取 app_key

从官网获取免费试用：

![豌豆HTTP试用页面](../static/images/wd_http_img.png)

选择套餐：

![选择套餐](../static/images/wd_http_img_4.png)

在个人中心的「开放接口」找到 `app_key`：

![app_key 位置](../static/images/wd_http_img_2.png)

### 配置代码

只需 1 个参数 `app_key`：

```python
# 文件地址： proxy/providers/wandou_http_proxy.py
def new_wandou_http_proxy() -> WanDouHttpProxy:
    return WanDouHttpProxy(
        app_key=os.getenv("wandou_app_key", "你的豌豆HTTP app_key"),
    )
```

### .env 配置

```bash
wandou_app_key=你的豌豆HTTP app_key
```

---

## 通用配置

在 `config/base_config.py` 中启用代理：

```python
ENABLE_IP_PROXY = True          # 开启代理
IP_PROXY_POOL_COUNT = 2         # 代理池数量
IP_PROXY_PROVIDER = "kuaidaili" # 选择：kuaidaili 或 wandou
```
