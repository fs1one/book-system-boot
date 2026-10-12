package com.first.book.service;

import com.first.book.entity.SysUser;

public interface SysUserService {

    SysUser login(String username, String userPwd);

    void regist(String username, String userPwd);
}
