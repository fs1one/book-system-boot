package com.first.book.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.Data;

@Data
@TableName("book")
public class Book {

    @TableId(value = "bid", type = IdType.AUTO)
    private Integer bid;

    private Integer uid;
    @NotBlank(message = "书名不能为空")
    private String title;

    private String author;

    @NotNull(message = "价格不能为空")
    @Positive(message = "价格必须大于 0")
    private Double price;

    private Integer status;
}
