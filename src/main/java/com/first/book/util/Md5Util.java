package com.first.book.util;

import java.security.MessageDigest;

public class Md5Util {

    public static String md5(String src){
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
