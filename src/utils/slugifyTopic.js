export function slugifyTopic(topic) {
    // 保留 Unicode 字母/数字（含中文）；否则纯中文 topic 被 [^\w-] strip
    // 成空串，导致 /topics/[topic] 生成非法空 param、build 报错。
    const slug = topic
        .toString()
        .toLowerCase()
        .replace(/ /g, "-")
        .replace(/[^\p{L}\p{N}_-]+/gu, "");
    return slug;
}

export function deslugifyTopic(slug) {
    const topic = slug.toString().replace(/-/g, " ");
    return topic;
}
