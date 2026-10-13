package com.first.book.controller;

import com.first.book.common.Result;
import com.first.book.dto.LoginDTO;
import com.first.book.dto.RegistDTO;
import com.first.book.entity.SysUser;
import com.first.book.exception.BizException;
import com.first.book.service.SysUserService;
import com.first.book.util.JwtUtil;
import com.first.book.util.UserContext;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@Tag(name = "用户管理", description = "注册、登录、当前登录人")
@RestController
@RequestMapping("/user")
public class SysUserController {

    private final SysUserService sysUserService;

    public SysUserController(SysUserService sysUserService){
        this.sysUserService = sysUserService;
    }

    @Operation(summary = "注册")
    @PostMapping("/regist")
    public Result<Void> regist(@RequestBody @Validated RegistDTO dto){

        sysUserService.regist(dto.getUsername(), dto.getUserPwd());

        return Result.success(null);
    }

    @Operation(summary = "登录", description = "成功后返回 token，填到文档页左侧「OpenAPI 鉴权」里再调试其他接口")
    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody @Validated LoginDTO dto){

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

    @Operation(summary = "当前登录人信息")
    @GetMapping("/info")
    public Result<Map<String, Object>> info() {

        Integer uid = UserContext.getUid();

        Map<String, Object> data = new HashMap<>();
        data.put("uid", uid);
        data.put("message", "token 有效，已通过拦截器");

        return Result.success(data);
    }
}
