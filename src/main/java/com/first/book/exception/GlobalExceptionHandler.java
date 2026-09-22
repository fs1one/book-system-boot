package com.first.book.exception;


import com.first.book.common.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BizException.class)
    public Result<Void> handleEizException(BizException e){
 
        log.warn("业务异常：{}",e.getMessage());
        return Result.error(e.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e){

        log.error("系统异常", e);
        return Result.error("异常繁忙，请稍后重试");
    }
}
