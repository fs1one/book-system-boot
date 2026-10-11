package com.first.book.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.first.book.entity.SysUser;
import com.first.book.mapper.SysUserMapper;
import org.springframework.stereotype.Service;

import java.security.MessageDigest;

@Service
public class SysUserServiceImpl implements SysUserService{

    private final SysUserMapper sysUserMapper;

    public SysUserServiceImpl(SysUserMapper sysUserMapper) {
        this.sysUserMapper = sysUserMapper;
    }

    @Override
    public SysUser login(String username, String userPwd) {

        QueryWrapper<SysUser> qw = new QueryWrapper<>();
        qw.eq("username", username);
        SysUser user = sysUserMapper.selectOne(qw);

        if (user == null){
            return null;
        }

        String inputMd5 = md5(userPwd);

        if(!inputMd5.equals(user.getUserPwd())){
            return null;
        }

        return user;
    }

    private String md5(String src){
        try{
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] bytes = md.digest(src.getBytes());

            char[] hexChars = {'0', '1', '2', '3', '4', '5', '6', '7',
                    '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'};

            char[] chars = new char[bytes.length * 2];
            int k = 0;
            for (byte b : bytes) {
                chars[k++] = hexChars[b >>> 4 & 0xf];
                chars[k++] = hexChars[b & 0xf];
            }
            return new String(chars);
        } catch (Exception e) {
            throw new RuntimeException("MD5 加密出错", e);
        }
    }
}
