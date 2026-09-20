package com.first.book.entity;


import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("sys_user")
public class SysUser {

    @TableId(value = "uid", type = IdType.AUTO)
    private Integer uid;

    private String username;

    private String userPwd;

}
