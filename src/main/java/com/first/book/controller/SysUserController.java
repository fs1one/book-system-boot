package com.first.book.controller;

import com.first.book.common.Result;
import com.first.book.entity.SysUser;
import com.first.book.exception.BizException;
import com.first.book.mapper.SysUserMapper;
import com.first.book.service.SysUserService;
import com.first.book.util.JwtUtil;
import com.first.book.util.UserContext;
import lombok.Data;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/user")
public class SysUserController {

    private final SysUserService sysUserService;

    public SysUserController(SysUserService sysUserService){
        this.sysUserService = sysUserService;
    }

    @Data
    public static class LoginDTO{
        private String username;
        private String userPwd;
    }

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody LoginDTO dto){

        if(dto.getUsername() == null || dto.getUsername().isBlank()
                || dto.getUserPwd() == null || dto.getUserPwd().isBlank()){
            throw new BizException("用户名和密码不能为空");
        }

        SysUser user = sysUserService.login(dto.getUsername(), dto.getUserPwd());

        if(user == null){
            throw new BizException("用户名或密码错误");
        }

        String token = JwtUtil.createToken(user.getUid(), user.getUsername());

        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("uid", user.getUid());
        data.put("username", user.getUsername());

        return Result.success(data);
    }

    @GetMapping("/info")
    public Result<Map<String, Object>> info() {

        Integer uid = UserContext.getUid();

        Map<String, Object> data = new HashMap<>();
        data.put("uid", uid);
        data.put("message", "token 有效，已通过拦截器");

        return Result.success(data);
    }
}
