package com.first.book.interceptor;

import com.first.book.exception.NotLoginException;
import com.first.book.util.JwtUtil;
import com.first.book.util.UserContext;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

@Slf4j
@Component
public class LoginInterceptor implements HandlerInterceptor {

    private static final String HEADER = "Authorization";
    private static final String PREFIX = "Bearer ";

    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler){

        String header = request.getHeader(HEADER);

        if(header == null || !header.startsWith(PREFIX)){
            throw new NotLoginException("未登录，请先登录");
        }

        String token = header.substring(PREFIX.length());

        Claims claims;
        try{
            claims = JwtUtil.parseToken(token);
        } catch (Exception e){
            log.warn("token 解析失败：{}", e.getMessage());
            throw new NotLoginException("登录已过期，请重新登录");
        }

        Integer uid = claims.get("uid", Integer.class);
        UserContext.set(uid);

        return true;
    }

    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex){
        UserContext.clear();
    }
}
