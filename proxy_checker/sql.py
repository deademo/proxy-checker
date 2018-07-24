_GET_PROXIES = """
SELECT *
FROM (
    SELECT proxy.id, check_result.id as check_id, proxy.protocol, proxy.host, proxy.port, check_result.is_passed, proxy.recheck_every, (
        SELECT COUNT(*) 
        FROM proxy_check_definition 
        WHERE proxy_check_definition.proxy_id = proxy.id
    ) as checks_count
    FROM proxy 
    LEFT JOIN check_result ON proxy.id = check_result.proxy_id 
    GROUP BY check_result.check_id, proxy.id
    ORDER BY check_result.done_at DESC
) as t
{where}
GROUP BY t.id
{having}
"""

GET_ALIVE_PROXIES = _GET_PROXIES.format(where='WHERE t.is_passed = TRUE', having='HAVING COUNT(*) = t.checks_count')
GET_PROXIES = _GET_PROXIES.format(where='', having='')

GET_BANNED_AT = """
SELECT proxy.id, check_definition.netloc
FROM proxy 
JOIN check_result ON proxy.id = check_result.proxy_id 
JOIN check_definition ON check_result.check_id = check_definition.id
WHERE check_result.is_passed = TRUE
AND check_result.is_banned = TRUE
GROUP BY check_result.check_id, proxy.id, check_definition.netloc, check_result.done_at
ORDER BY check_result.done_at DESC
"""


GET_PROXY_CHECKS = """
SELECT pcd.proxy_id, pcd.check_definition_id, cd.name
FROM proxy_check_definition pcd
INNER JOIN check_definition cd ON cd.id = pcd.check_definition_id
"""
