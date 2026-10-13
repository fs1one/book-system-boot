package com.first.book.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class RegistDTO {

    @Schema(description = "用户名", example = "day7test")
    @NotBlank(message = "用户名不能为空")
    private String username;

    @Schema(description = "密码", example = "abc123456")
    @NotBlank(message = "密码不能为空")
    private String userPwd;
}
