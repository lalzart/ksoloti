/**
 * Copyright (C) 2026 Ksoloti contributors
 *
 * This file is part of Axoloti.
 *
 * Axoloti is free software: you can redistribute it and/or modify it under the
 * terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later
 * version.
 */

package axoloti;

/**
 * Identifies this source tree as the local fork without changing the upstream
 * 1.1 compatibility version.
 */
public final class BuildIdentity {

    public static final String EDITION = "Local Fork";
    public static final int SINGLE_INSTANCE_PORT = 55577;

    private BuildIdentity() {
    }

    public static String applicationTitle(String applicationName) {
        return applicationName + " \u00b7 " + EDITION;
    }

    public static String buildVersion(String version) {
        return version + " \u00b7 " + EDITION;
    }
}
