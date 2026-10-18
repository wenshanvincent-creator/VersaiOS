#include <BleComboKeyboard.h>
#include <BleComboMouse.h>
#include <BLEDevice.h>

BleComboKeyboard bleKeyboard("VersaiOS Mouse", "Apple", 100);
BleComboMouse bleMouse(&bleKeyboard);

// 改为动态变量，默认值给个大概即可，实际会由 Python 覆盖
long screen_max_x = 2000;
long screen_max_y = 4000;
bool was_connected = false;

void setup() {
    Serial.begin(115200);
    Serial.println(">>> [系统] 正在初始化 VersaiOS BLE 动态鼠标引擎...");
    bleKeyboard.begin();
}

void move_relative_safe(long dx, long dy, int step_limit = 100) {
    while (dx != 0 || dy != 0) {
        int8_t step_x = 0;
        int8_t step_y = 0;

        if (dx > step_limit) step_x = step_limit;
        else if (dx < -step_limit) step_x = -step_limit;
        else step_x = dx;

        if (dy > step_limit) step_y = step_limit;
        else if (dy < -step_limit) step_y = -step_limit;
        else step_y = dy;

        bleMouse.move(step_x, step_y);
        dx -= step_x;
        dy -= step_y;

        delay(8); // 防止蓝牙拥堵
    }
}

// 使用动态变量进行中线十字校准
void perform_center_cross_calibration() {
    move_relative_safe(0, screen_max_y * 2);
    delay(50);
    move_relative_safe(0, -screen_max_y / 2);
    delay(50);
    move_relative_safe(-screen_max_x * 2, 0);
    delay(50);
    move_relative_safe(screen_max_x / 2, 0);
    delay(50);
}

void loop() {
    bool connected = bleKeyboard.isConnected();
    if (was_connected && !connected) {
        BLEDevice::startAdvertising();
    }
    was_connected = connected;
    if (connected && Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();

        int x, y;

        // 1. 动态配置指令
        if (sscanf(cmd.c_str(), "KEY:%d,%d", &x, &y) == 2) {
            if (x >= 0 && x <= 255 && y > 0 && y <= 0x65) {
                KeyReport report = {};
                report.modifiers = x;
                report.keys[0] = y;
                bleKeyboard.sendReport(&report);
                delay(70);
                bleKeyboard.releaseAll();
                delay(30);
                Serial.println(">>> [执行] 按键完成");
            }
        }
        else if (sscanf(cmd.c_str(), "SET:%d,%d", &x, &y) == 2) {
            screen_max_x = x;
            screen_max_y = y;
            Serial.printf(">>> [配置] 收到 Python 下发参数: 最大步数 X=%ld, Y=%ld\n", screen_max_x, screen_max_y);
        }
        // 2. 交互测试指令（供 GUI 校准模块使用）
        else if (sscanf(cmd.c_str(), "REL:%d,%d", &x, &y) == 2) {
            move_relative_safe(x, y);
            Serial.printf(">>> [测试] 纯相对移动: dx=%d, dy=%d\n", x, y);
        }
        else if (sscanf(cmd.c_str(), "FINE:%d,%d", &x, &y) == 2) {
            move_relative_safe(x, y, 4);
            Serial.println(">>> [执行] 精细移动完成");
        }
        else if (sscanf(cmd.c_str(), "SCROLL:%d", &x) == 1) {
            if (x != 0 && x >= -24 && x <= 24) {
                int direction = x > 0 ? 1 : -1;
                for (int i = 0; i < abs(x); ++i) {
                    bleMouse.move(0, 0, direction);
                    delay(30);
                }
                Serial.println(">>> [执行] 滚轮完成");
            }
        }
        else if (cmd == "TAP") {
            bleMouse.click();
            Serial.println(">>> [执行] 原地点击完成！");
        }
        else if (sscanf(cmd.c_str(), "BUTTON:%d", &x) == 1) {
            if (x == 1 || x == 2 || x == 4 || x == 8 || x == 16) {
                bleMouse.click(x);
                Serial.println(">>> [执行] 辅助按键完成");
            }
        }
        else if (cmd == "LONG") {
            bleMouse.press(MOUSE_LEFT);
            delay(800);
            bleMouse.release(MOUSE_LEFT);
            Serial.println(">>> [执行] 长按完成");
        }
        else if (sscanf(cmd.c_str(), "DRAG:%d,%d", &x, &y) == 2) {
            bleMouse.press(MOUSE_LEFT);
            delay(80);
            int steps = max(abs(x), abs(y)) / 8 + 1;
            long previous_x = 0, previous_y = 0;
            for (int i = 1; i <= steps; ++i) {
                long next_x = (long)x * i / steps;
                long next_y = (long)y * i / steps;
                bleMouse.move(next_x - previous_x, next_y - previous_y);
                previous_x = next_x;
                previous_y = next_y;
                delay(16);
            }
            delay(80);
            bleMouse.release(MOUSE_LEFT);
            Serial.println(">>> [执行] 拖动完成");
        }
        // 3. 核心击发指令（供主程序 main_versaios.py 使用）
        else if (sscanf(cmd.c_str(), "CLICK:%d,%d", &x, &y) == 2) {
            Serial.printf(">>> [指令] 收到点击任务: 目标 (%d, %d)\n", x, y);

            perform_center_cross_calibration(); // 根据 SET 收到的参数进行归零

            long center_x = screen_max_x / 2;
            long center_y = screen_max_y / 2;
            long move_dx = x - center_x;
            long move_dy = y - center_y;

            move_relative_safe(move_dx, move_dy);
            delay(50);
            bleMouse.click();
            Serial.println(">>> [执行] 点击完成！");
        }
    }
    delay(10);
}
