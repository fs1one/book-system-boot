package com.first.book.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("Book")
public class Book {

    @TableId(value = "bid", type = IdType.AUTO)
    private Integer bid;

    private Integer uid;
    private String title;
    private String author;
    private Double price;
    private Integer status;
}
