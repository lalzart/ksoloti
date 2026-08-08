/**
 * Copyright (C) 2013, 2014, 2015 Johannes Taelman
 * Edited 2023 - 2026 by Ksoloti contributors
 *
 * This file is part of Axoloti.
 *
 * Axoloti is free software: you can redistribute it and/or modify it under the
 * terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later
 * version.
 */
package axoloti;

import axoloti.object.AxoObjects;
import axoloti.utils.FirmwareID;
import axoloti.utils.Preferences;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.simpleframework.xml.Serializer;
import org.simpleframework.xml.core.Persister;
import org.simpleframework.xml.stream.Format;
import qcmds.QCmdCompilePatch;

/** Offline AXP-to-Cortex-M4 compile/link entry point with structured output. */
public final class HeadlessPatchCompiler {
    private static final Pattern MEMORY_REGION = Pattern.compile(
            "^([A-Za-z0-9_*]+)\\s+(0x[0-9a-fA-F]+)\\s+(0x[0-9a-fA-F]+)\\s*(.*)$");
    private static final Pattern MEMORY_USAGE = Pattern.compile(
            "^\\s*([^:]+):\\s+([0-9.]+)\\s+([A-Za-z]+)\\s+([0-9.]+)\\s+([A-Za-z]+)\\s+([0-9.]+)%\\s*$");

    private HeadlessPatchCompiler() {
    }

    public static boolean isRequested(String[] args) {
        for (String arg : args) {
            if ("-compileOnly".equalsIgnoreCase(arg)) {
                return true;
            }
        }
        return false;
    }

    public static int run(String[] args) {
        System.setProperty("java.awt.headless", "true");
        String inputArgument = null;
        for (int i = 0; i < args.length; i++) {
            if ("-compileOnly".equalsIgnoreCase(args[i])) {
                if (i + 1 < args.length) {
                    inputArgument = args[i + 1];
                }
                break;
            }
        }
        if (inputArgument == null || inputArgument.isEmpty()) {
            emitFailure("E_COMPILE_ARGUMENT", "-compileOnly requires one .axp path", null);
            return 2;
        }

        File input = new File(inputArgument).getAbsoluteFile();
        if (!input.isFile() || !input.canRead()) {
            emitFailure("E_COMPILE_INPUT", "patch is not a readable file", input);
            return 2;
        }
        if (!input.getName().toLowerCase(Locale.ROOT).endsWith(".axp")) {
            emitFailure("E_COMPILE_FORMAT", "compile-only currently accepts .axp files", input);
            return 2;
        }

        try {
            System.setProperty("axoloti.deterministic_source_sha256", sha256(input));
            Axoloti.initProperties(false);
            Preferences.LoadPreferences();
            Synonyms.instance();

            String firmwareId = FirmwareID.getFirmwareID();
            if (!firmwareId.matches("[0-9A-F]{8}")) {
                emitFailure(
                        "E_LINK_FIRMWARE_BASELINE",
                        "authenticated prebuilt firmware image is missing or unreadable under "
                                + System.getProperty(Axoloti.LINK_FIRMWARE_DIR),
                        input);
                return 2;
            }

            MainFrame.axoObjects = new AxoObjects();
            MainFrame.axoObjects.LoadAxoObjects();
            MainFrame.axoObjects.LoaderThread.join();
            loadExtraObjectPaths(MainFrame.axoObjects);

            Serializer serializer = new Persister(new Format(2));
            Patch patch = serializer.read(Patch.class, input);
            patch.setFileNamePath(input.getPath());
            patch.PostContructor();
            patch.WriteCode();

            File cpp = patch.getCppFile();
            File bin = patch.getBinFile();
            File sram3 = patch.getBinFile_sram3();
            String stem = stripSuffix(bin.getAbsolutePath(), ".bin");
            File map = new File(stem + ".map");
            deleteExactArtifact(bin);
            deleteExactArtifact(sram3);
            deleteExactArtifact(map);

            QCmdCompilePatch command = new QCmdCompilePatch(patch);
            command.Do(null);
            boolean ok = command.success() && bin.isFile();
            emitResult(
                    ok, input, cpp, bin, sram3, map,
                    MainFrame.axoObjects.ObjectList.size(), command.getOutputLines());
            return ok ? 0 : 2;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            emitFailure("E_COMPILE_INTERRUPTED", ex.getMessage(), input);
            return 2;
        } catch (Exception ex) {
            emitFailure("E_COMPILE_EXCEPTION", ex.toString(), input);
            ex.printStackTrace(System.err);
            return 2;
        }
    }

    private static void deleteExactArtifact(File file) throws IOException {
        Files.deleteIfExists(file.toPath());
    }

    private static void loadExtraObjectPaths(AxoObjects objects) {
        String configured = System.getProperty("ksai.object_paths", "");
        if (configured.isEmpty()) {
            return;
        }
        for (String value : configured.split(Pattern.quote(File.pathSeparator))) {
            if (value.isEmpty()) {
                continue;
            }
            File path = new File(value);
            File objectsPath = new File(path, "objects");
            File loadPath = objectsPath.isDirectory() ? objectsPath : path;
            if (!loadPath.isDirectory()) {
                throw new IllegalArgumentException("extra object path is not a directory: " + value);
            }
            objects.LoadAxoObjects(loadPath.getPath());
        }
    }

    private static String stripSuffix(String value, String suffix) {
        return value.endsWith(suffix) ? value.substring(0, value.length() - suffix.length()) : value;
    }

    private static void emitResult(
            boolean ok,
            File input,
            File cpp,
            File bin,
            File sram3,
            File map,
            int objectCount,
            List<String> compilerOutput) {
        StringBuilder json = new StringBuilder();
        json.append('{');
        field(json, "ok", ok ? "true" : "false", false);
        field(json, "command", quote("compile-only"), true);
        field(json, "input", quote(input.getAbsolutePath()), true);
        field(json, "input_sha256", quote(sha256(input)), true);
        field(json, "loaded_object_variants", Integer.toString(objectCount), true);
        json.append(",\"baseline\":{");
        field(json, "firmware_id", quote(FirmwareID.getFirmwareID()), false);
        field(json, "firmware_source", quote(System.getProperty(Axoloti.FIRMWARE_DIR)), true);
        field(json, "link_firmware", quote(System.getProperty(Axoloti.LINK_FIRMWARE_DIR)), true);
        field(json, "platform", quote(System.getProperty(Axoloti.PLATFORM_DIR)), true);
        json.append('}');
        json.append(",\"evidence\":{");
        field(json, "legacy_java_deserialize", quote("pass"), false);
        field(json, "cpp_generation", quote(cpp.isFile() ? "pass" : "fail"), true);
        field(json, "arm_compile_link", quote(ok ? "pass" : "fail"), true);
        field(json, "usb_connection", quote("not_attempted"), true);
        field(json, "connected_board", quote("not_run"), true);
        field(json, "audible", quote("not_run"), true);
        json.append('}');
        json.append(",\"artifacts\":{");
        field(json, "cpp", artifact(cpp), false);
        field(json, "bin", artifact(bin), true);
        field(json, "sram3", artifact(sram3), true);
        field(json, "map", artifact(map), true);
        json.append('}');
        json.append(",\"memory_regions\":").append(memoryRegions(map));
        json.append(",\"memory_usage\":").append(memoryUsage(compilerOutput));
        json.append(",\"diagnostics\":[");
        if (!ok) {
            json.append("{\"severity\":\"error\",\"code\":\"E_ARM_COMPILE_LINK\",\"message\":")
                    .append(quote("compiler or linker did not produce the patch binary"))
                    .append(",\"context\":{\"compiler_output\":")
                    .append(compilerDiagnostics(compilerOutput))
                    .append('}')
                    .append('}');
        }
        json.append("]}");
        System.out.println(json.toString());
    }

    private static String compilerDiagnostics(List<String> compilerOutput) {
        List<String> selected = new ArrayList<String>();
        for (String line : compilerOutput) {
            String lower = line.toLowerCase(Locale.ROOT);
            if (lower.contains("error:")
                    || lower.contains("undefined reference")
                    || lower.startsWith("make: ***")) {
                String compact = line.trim();
                if (compact.length() > 400) {
                    compact = compact.substring(0, 400);
                }
                selected.add(quote(compact));
                if (selected.size() == 6) {
                    break;
                }
            }
        }
        return "[" + String.join(",", selected) + "]";
    }

    private static String artifact(File file) {
        return "{\"path\":" + quote(file.getAbsolutePath())
                + ",\"exists\":" + (file.isFile() ? "true" : "false")
                + ",\"bytes\":" + (file.isFile() ? file.length() : 0)
                + ",\"sha256\":" + quote(sha256(file)) + "}";
    }

    private static String memoryRegions(File map) {
        if (!map.isFile()) {
            return "[]";
        }
        List<String> regions = new ArrayList<String>();
        boolean inConfiguration = false;
        try {
            for (String line : Files.readAllLines(map.toPath(), StandardCharsets.UTF_8)) {
                if (line.trim().equals("Memory Configuration")) {
                    inConfiguration = true;
                    continue;
                }
                if (inConfiguration && line.trim().equals("Linker script and memory map")) {
                    break;
                }
                if (!inConfiguration || line.trim().isEmpty() || line.startsWith("Name")) {
                    continue;
                }
                Matcher matcher = MEMORY_REGION.matcher(line.trim());
                if (matcher.matches()) {
                    regions.add("{\"name\":" + quote(matcher.group(1))
                            + ",\"origin\":" + quote(matcher.group(2))
                            + ",\"length\":" + quote(matcher.group(3))
                            + ",\"attributes\":" + quote(matcher.group(4).trim()) + "}");
                }
            }
        } catch (IOException ex) {
            return "[]";
        }
        return "[" + String.join(",", regions) + "]";
    }

    private static String memoryUsage(List<String> compilerOutput) {
        List<String> rows = new ArrayList<String>();
        for (String line : compilerOutput) {
            Matcher matcher = MEMORY_USAGE.matcher(line);
            if (matcher.matches()) {
                rows.add("{\"name\":" + quote(matcher.group(1).trim())
                        + ",\"used\":" + quote(
                                Double.parseDouble(matcher.group(2)) == 0.0
                                        ? "0 B" : matcher.group(2) + " " + matcher.group(3))
                        + ",\"capacity\":" + quote(matcher.group(4) + " " + matcher.group(5))
                        + ",\"percent\":" + matcher.group(6) + "}");
            }
        }
        return "[" + String.join(",", rows) + "]";
    }

    private static String sha256(File file) {
        if (file == null || !file.isFile()) {
            return "";
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[65536];
            try (java.io.InputStream input = Files.newInputStream(file.toPath())) {
                int count;
                while ((count = input.read(buffer)) >= 0) {
                    digest.update(buffer, 0, count);
                }
            }
            StringBuilder value = new StringBuilder();
            for (byte item : digest.digest()) {
                value.append(String.format("%02x", item & 0xff));
            }
            return value.toString();
        } catch (Exception ex) {
            return "";
        }
    }

    private static void emitFailure(String code, String message, File input) {
        StringBuilder json = new StringBuilder();
        json.append("{\"ok\":false,\"command\":\"compile-only\"");
        if (input != null) {
            json.append(",\"input\":").append(quote(input.getAbsolutePath()));
        }
        json.append(",\"evidence\":{\"arm_compile_link\":\"not_run\",\"usb_connection\":\"not_attempted\",\"connected_board\":\"not_run\",\"audible\":\"not_run\"}");
        json.append(",\"diagnostics\":[{\"severity\":\"error\",\"code\":")
                .append(quote(code)).append(",\"message\":").append(quote(message == null ? "" : message))
                .append("}]}");
        System.out.println(json.toString());
    }

    private static void field(StringBuilder json, String name, String value, boolean comma) {
        if (comma) {
            json.append(',');
        }
        json.append(quote(name)).append(':').append(value);
    }

    private static String quote(String value) {
        StringBuilder escaped = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '\\': escaped.append("\\\\"); break;
                case '"': escaped.append("\\\""); break;
                case '\n': escaped.append("\\n"); break;
                case '\r': escaped.append("\\r"); break;
                case '\t': escaped.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        escaped.append(String.format("\\u%04x", (int) c));
                    } else {
                        escaped.append(c);
                    }
            }
        }
        return escaped.append('"').toString();
    }
}
