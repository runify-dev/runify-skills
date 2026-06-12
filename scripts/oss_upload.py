#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oss_upload — 把本地图片上传到对象存储，返回【公网可访问的 presigned 短时 URL】。
仅用于“图片理解/自检”：agnes-2.0-flash 的图片理解只吃公网 URL、不支持 base64，
桌面端本地图必须先换成公网直链。图生图/润色/图生视频不需要它（那些支持 base64）。

按 provider 分派三家 SDK：
  aliyun     -> oss2                 (pip install oss2)
  tencent    -> cos-python-sdk-v5    (pip install cos-python-sdk-v5)
  volcengine -> tos                  (pip install tos)
凭据由 SKILL.md 的 skillParameterForm 注入为同名环境变量（provider / ali_* / tencent_* / volc_*）。

用法:
  python oss_upload.py --file /path/to/img.png
  python oss_upload.py --file img.png --expires 1800   # 直链有效期秒数（默认 1800=30min）

返回 RESULT_JSON: {url, provider, key, expires}
注意：
  - endpoint 必须用公网域名（勿用内网 -internal），否则 agnes 服务器拉不到。
  - presigned URL 到期自动失效；agnes 只在生成那一刻拉一次，30 分钟足够。
"""
import os, sys, time, uuid, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import emit, fail, log

STAGE = "oss_upload"

def _env(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v.strip()
    return ""

def _key_for(local_path):
    ext = os.path.splitext(local_path)[1] or ".png"
    return f"runify-tmp/{time.strftime('%Y%m%d')}/{uuid.uuid4().hex}{ext}"


# 各 provider 必填字段（endpoint 与 region 至少其一时单列）
_REQUIRED = {
    "aliyun":     {"keys": ["ali_access_key_id", "ali_access_key_secret", "ali_bucket"],
                   "either": ["ali_endpoint", "ali_region"], "label": "阿里云 OSS"},
    "tencent":    {"keys": ["tencent_secret_id", "tencent_secret_key", "tencent_bucket", "tencent_region"],
                   "either": [], "label": "腾讯云 COS"},
    "volcengine": {"keys": ["volc_access_key", "volc_secret_key", "volc_bucket", "volc_region"],
                   "either": ["volc_endpoint", "volc_region"], "label": "火山引擎 TOS"},
}

def _needs_config(message, missing=None, provider=None):
    """配置缺失：不是 error，而是引导用户去技能界面配置。agent 应据此提示用户。"""
    payload = {"status": "needs_config", "stage": STAGE, "message": message,
               "where": "Runify 技能设置界面 → 本技能参数配置",
               "guidance": "请在技能设置里选择 OSS 供应商并填写凭据后重试（图片理解需要把本地图临时上传换公网 URL）。",
               "missing": missing or [], "provider": provider}
    print("RESULT_JSON: " + json.dumps(payload, ensure_ascii=False), flush=True)
    sys.exit(0)   # 退出码 0（成功通道）：数据在 stdout，让"只读成功日志(stdout)"的调用方能拿到这条配置指引

def check_oss_config():
    """检查 ENV 里 OSS 是否配齐。未配齐 -> 直接 _needs_config 出指引（不再继续）。"""
    provider = _env("provider")
    if not provider:
        _needs_config("尚未选择 OSS 供应商。图片理解需要把本地图临时上传换公网 URL。",
                      missing=["provider"])
    spec = _REQUIRED.get(provider)
    if not spec:
        _needs_config(f"不支持的 OSS 供应商：{provider}（仅 aliyun/tencent/volcengine）",
                      provider=provider)
    missing = [k for k in spec["keys"] if not _env(k)]
    if spec["either"] and not any(_env(k) for k in spec["either"]):
        missing.append(" 或 ".join(spec["either"]))
    if missing:
        _needs_config(f"{spec['label']} 配置不全，缺少：{', '.join(missing)}。",
                      missing=missing, provider=provider)
    return provider


def _up_aliyun(local, key, expires):
    try:
        import oss2
    except ImportError:
        fail(STAGE, "缺少依赖：pip install oss2")
    ak = _env("ali_access_key_id"); sk = _env("ali_access_key_secret")
    bucket_name = _env("ali_bucket"); region = _env("ali_region")
    endpoint = _env("ali_endpoint") or (f"https://oss-{region}.aliyuncs.com" if region else "")
    if not (ak and sk and bucket_name and endpoint):
        fail(STAGE, "阿里云配置不全（需 ak/secret/bucket/endpoint 或 region）")
    if not endpoint.startswith("http"):
        endpoint = "https://" + endpoint
    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    bucket.put_object_from_file(key, local)
    return bucket.sign_url("GET", key, expires, slash_safe=True)


def _up_tencent(local, key, expires):
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        fail(STAGE, "缺少依赖：pip install cos-python-sdk-v5")
    sid = _env("tencent_secret_id"); skey = _env("tencent_secret_key")
    bucket = _env("tencent_bucket"); region = _env("tencent_region")
    endpoint = _env("tencent_endpoint")
    if not (sid and skey and bucket and region):
        fail(STAGE, "腾讯云配置不全（需 secret_id/secret_key/bucket/region）")
    conf_kw = {"Region": region, "SecretId": sid, "SecretKey": skey}
    if endpoint:
        conf_kw["Endpoint"] = endpoint
    client = CosS3Client(CosConfig(**conf_kw))
    client.upload_file(Bucket=bucket, Key=key, LocalFilePath=local)
    return client.get_presigned_url(Method="GET", Bucket=bucket, Key=key, Expired=expires)


def _up_volc(local, key, expires):
    try:
        import tos
    except ImportError:
        fail(STAGE, "缺少依赖：pip install tos")
    ak = _env("volc_access_key"); sk = _env("volc_secret_key")
    bucket = _env("volc_bucket"); region = _env("volc_region")
    endpoint = _env("volc_endpoint") or (f"tos-{region}.volces.com" if region else "")
    if not (ak and sk and bucket and region and endpoint):
        fail(STAGE, "火山配置不全（需 ak/sk/bucket/region/endpoint）")
    client = tos.TosClientV2(ak, sk, endpoint, region)
    client.put_object_from_file(bucket, key, local)
    out = client.pre_signed_url(tos.HttpMethodType.Http_Method_Get, bucket, key, expires=expires)
    return out.signed_url


_DISPATCH = {"aliyun": _up_aliyun, "tencent": _up_tencent, "volcengine": _up_volc}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None)
    ap.add_argument("--expires", type=int, default=1800)
    ap.add_argument("--check-only", action="store_true", help="只校验 OSS 配置是否齐全，不上传")
    a = ap.parse_args()

    if a.check_only:
        provider = check_oss_config()   # 不齐会出 needs_config 并退出
        emit({"stage": STAGE, "configured": True, "provider": provider})

    if not a.file:
        fail(STAGE, "需要 --file（或用 --check-only 仅校验配置）")
    if not os.path.exists(a.file):
        fail(STAGE, f"文件不存在：{a.file}")
    provider = check_oss_config()   # 未配齐会直接出 needs_config 指引并退出
    fn = _DISPATCH[provider]

    key = _key_for(a.file)
    log(f"上传到 {provider} … key={key}")
    try:
        url = fn(a.file, key, a.expires)
    except SystemExit:
        raise
    except Exception as e:
        fail(STAGE, f"上传失败：{e}", provider=provider)
    log("  ✓ 直链已生成")
    emit({"stage": STAGE, "provider": provider, "key": key,
          "url": url, "expires": a.expires})

if __name__ == "__main__":
    main()
