package com.first.book.exception;


import com.first.book.common.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.List;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BizException.class)
    public Result<Void> handleBizException(BizException e){

        log.warn("业务异常：{}",e.getMessage());
        return Result.error(e.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e){

        log.error("系统异常", e);
        return Result.error("异常繁忙，请稍后重试");
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleMethodArgumentNotValidException(MethodArgumentNotValidException e){

        List<FieldError> fieldErrors = e.getBindingResult().getFieldErrors();

        StringBuilder sb = new StringBuilder();
        for (FieldError fe : fieldErrors) {
            if(sb.length() > 0){
                sb.append("；");
            }
            sb.append(fe.getDefaultMessage());
        }

        log.warn("参数校验失败：{}", sb);
        return Result.error(sb.toString());
    }
}
