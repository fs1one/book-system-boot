package com.first.book.util;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

public class JwtUtil {

    private static final String SECRET = "book-system-boot-jwt-secret-key-2026-fs1one";

    private static final long EXPIRE_MS = 7 * 24 * 60 * 60 * 1000L;

    private static final SecretKey KEY = Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8));


    public static String createToken(Integer uid, String username){

        Date now = new Date();
        Date expire = new Date(now.getTime() + EXPIRE_MS);

        return Jwts.builder()
                .subject(username)
                .claim("uid", uid)
                .issuedAt(now)
                .expiration(expire)
                .signWith(KEY)
                .compact();
    }

    public static Claims parseToken(String token) {
        return Jwts.parser()
                .verifyWith(KEY)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
