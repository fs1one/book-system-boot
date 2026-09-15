package com.first.book.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.HashMap;
import java.util.Map;

/**
 * 第一个接口，用来验证环境有没有跑通
 */
@RestController
public class HelloController {

    @GetMapping("/hello")
    public Map<String, Object> hello() {
        Map<String, Object> map = new HashMap<>();
        map.put("code", 200);
        map.put("message", "Spring Boot 跑起来了");
        map.put("data", "Hello Spring Boot");
        return map;
    }
}