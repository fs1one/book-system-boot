package com.first.book.controller;

import com.first.book.properties.MyappProperties;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

/**
 * 第一个接口，用来验证环境有没有跑通
 */
@RestController
public class HelloController {

    private final MyappProperties props;

    public HelloController(MyappProperties props) {
        this.props = props;
    }

    @GetMapping("/hello")
    public Map<String, Object> hello() {
        Map<String, Object> map = new HashMap<>();
        map.put("code", 200);
        map.put("message", "Spring Boot 跑起来了");
        map.put("data", "Hello Spring Boot");
        map.put("project_name", props.getProjectName());
        map.put("version", props.getVersion());
        map.put("user", props.getUser());
        map.put("destination", props.getDestination());
        return map;
    }
}
