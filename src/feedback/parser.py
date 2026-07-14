import re


def parse_test_output(output: str) -> list[dict]:
    """
    解析测试输出，支持 pytest 和 unittest 格式。
    冷启动修复：增加退出码判定 + unittest 格式 + 回退解析。
    """
    failures = []
    if not output:
        return failures

    # 方法1: pytest 格式 (FAILED 行 + FAILURES 分隔符)
    fail_pattern = re.compile(r"^(.+?)\s+FAILED", re.MULTILINE)
    fail_files = fail_pattern.findall(output)

    failure_section = re.split(r"=+\s+FAILURES\s+=+", output)

    if len(failure_section) >= 2:
        failure_text = failure_section[1]
        for fname in fail_files:
            fname_clean = fname.strip()
            file_name = fname_clean.split("::")[0] if "::" in fname_clean else fname_clean
            failure_info = {"file": file_name, "line": None, "message": ""}
            line_match = re.search(rf"{re.escape(fname_clean)}.*?:(\d+):", failure_text)
            if line_match:
                failure_info["line"] = int(line_match.group(1))
            failure_info["message"] = failure_text[:500].strip()
            failures.append(failure_info)
        return failures

    # 方法2: unittest 格式
    unittest_pattern = re.compile(r"FAIL:\s+(.+?)\s+\((.+?)\)", re.MULTILINE)
    unittest_fails = unittest_pattern.findall(output)
    if unittest_fails:
        for test_name, module in unittest_fails:
            failures.append({
                "file": module,
                "line": None,
                "message": output[:500].strip(),
            })
        return failures

    # 方法3: 回退——通过 exit_code 或 error/fail 关键词判定
    if re.search(r"(FAILED|ERRORS|FAIL:|error:)", output, re.IGNORECASE):
        failures.append({
            "file": "",
            "line": None,
            "message": output[:500].strip(),
        })

    return failures