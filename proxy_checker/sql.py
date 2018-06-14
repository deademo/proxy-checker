GET_ALIVE_PROXIES = """
SELECT *
FROM (
    SELECT proxy.*, check_result.*, (
        SELECT COUNT(*) 
        FROM proxy_check_definition 
        WHERE proxy_check_definition.proxy_id = proxy.id
    ) as checks_count
    FROM proxy 
    JOIN check_result ON proxy.id = check_result.proxy_id 
    GROUP BY check_result.check_id, proxy.id
    ORDER BY check_result.done_at DESC
) as t
WHERE t.is_passed = 1
GROUP BY t.id
HAVING COUNT(*) = t.checks_count
"""

GET_BANNED_AT = """
SELECT proxy.id, check_definition.netloc
FROM proxy 
JOIN check_result ON proxy.id = check_result.proxy_id 
JOIN check_definition ON check_result.check_id = check_definition.id
WHERE check_result.is_passed = 1
AND check_result.is_banned = 1
GROUP BY check_result.check_id, proxy.id
ORDER BY check_result.done_at DESC
"""
