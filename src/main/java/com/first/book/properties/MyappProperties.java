package com.first.book.properties;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 对应 application.yaml 里的 myapp 节点。
 * @ConfigurationProperties 负责把 yaml 里的值"绑"进来，
 * @Component 负责让 Spring 把它当成一个 bean 管起来（这样别处才能注入它）。
 */
@Component
@ConfigurationProperties(prefix = "myapp")
public class MyappProperties {

    private String projectName;
    private String version;
    private Object user;
    private String code;
    private String destination;

    public String getProjectName() {
        return projectName;
    }

    public void setProjectName(String projectName) {
        this.projectName = projectName;
    }

    public String getVersion() {
        return version;
    }

    public void setVersion(String version) {
        this.version = version;
    }

    public Object getUser() {
        return user;
    }

    public void setUser(Object user) {
        this.user = user;
    }

    public String getCode() {
        return code;
    }

    public void setCode(String code) {
        this.code = code;
    }

    public String getDestination() {
        return destination;
    }

    public void setDestination(String destination) {
        this.destination = destination;
    }
}
