// SPDX-License-Identifier: GPL-3.0-or-later

import axoloti.Patch;
import axoloti.utils.Preferences;
import java.nio.file.Path;
import org.simpleframework.xml.Serializer;
import org.simpleframework.xml.core.Persister;
import org.simpleframework.xml.stream.Format;

/** Offline-only SimpleXML compatibility check for generated legacy patches. */
public final class AxpDeserializeCheck {
    private AxpDeserializeCheck() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.err.println("usage: AxpDeserializeCheck PATCH.axp");
            System.exit(2);
        }
        Path input = Path.of(args[0]).toAbsolutePath().normalize();
        // Parameter UI construction asks for font preferences. Seed an in-memory
        // instance so deserialization cannot initialize or synchronize libraries.
        Preferences.setInstance(new Preferences());
        Serializer serializer = new Persister(new Format(2));
        Patch patch = serializer.read(Patch.class, input.toFile());
        int objects = patch.GetObjectInstancesWithoutComments().size();
        int nets = patch.nets.size();
        System.out.printf(
            "{\"ok\":true,\"legacy_java_deserialize\":\"pass\",\"objects\":%d,\"nets\":%d}%n",
            objects,
            nets
        );
    }
}
