package com.first.book.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.Data;

@Schema(description = "图书")
@Data
@TableName("book")
public class Book {

    @Schema(description = "图书 id(新增不用传)", example = "1")
    @TableId(value = "bid", type = IdType.AUTO)
    private Integer bid;

    @Schema(description = "所属用户 id", example = "1")
    private Integer uid;

    @Schema(description = "书名", example = "三体")
    @NotBlank(message = "书名不能为空")
    private String title;

    @Schema(description = "作者", example = "刘慈欣")
    private String author;

    @Schema(description = "价格", example = "45.5")
    @NotNull(message = "价格不能为空")
    @Positive(message = "价格必须大于 0")
    private Double price;

    @Schema(description = "状态：0 未读，1 已读", example = "0")
    private Integer status;
}
