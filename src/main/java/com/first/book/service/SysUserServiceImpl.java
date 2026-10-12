package com.first.book.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.first.book.entity.SysUser;
import com.first.book.exception.BizException;
import com.first.book.mapper.SysUserMapper;
import com.first.book.util.Md5Util;
import org.springframework.stereotype.Service;


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

        String inputMd5 = Md5Util.md5(userPwd);

        if(!inputMd5.equals(user.getUserPwd())){
            return null;
        }

        return user;
    }

    @Override
    public void regist(String username, String userPwd){

        QueryWrapper<SysUser> qw = new QueryWrapper<>();
        qw.eq("username", username);

        if(sysUserMapper.selectOne(qw) != null){
            throw new BizException("用户名已存在");
        }

        SysUser user = new SysUser();
        user.setUsername(username);
        user.setUserPwd(Md5Util.md5(userPwd));

        int rows = sysUserMapper.insert(user);
        if(rows == 0){
            throw new BizException("注册失败，请稍后重试");
        }
    }
}
