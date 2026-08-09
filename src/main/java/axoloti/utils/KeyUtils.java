package axoloti.utils;

import java.awt.GraphicsEnvironment;
import java.awt.Toolkit;
import java.awt.event.InputEvent;
import java.awt.event.KeyEvent;
import javax.swing.KeyStroke;

public class KeyUtils {
    public static Boolean isKeyCodeControlOrCommand(KeyEvent ke) {
        return KeyStroke.getKeyStrokeForEvent(ke).equals(
                KeyStroke.getKeyStroke(ke.getKeyCode(), CONTROL_OR_CMD_MASK))
                || (ke.getKeyCode() == KeyEvent.VK_CONTROL || ke.getKeyCode() == KeyEvent.VK_META);
    }
    
    public static Boolean isControlOrCommandDown(InputEvent me) {
        return me.isMetaDown() || me.isControlDown();
    }
    
    public static Boolean isIgnoreModifierDown(KeyEvent ke) {
        return ke.isAltDown() || ke.isAltGraphDown() || ke.isControlDown() || ke.isMetaDown();
    }
    
    private static int getControlOrCommandMask() {
        if (GraphicsEnvironment.isHeadless()) {
            return OSDetect.getOS() == OSDetect.OS.MAC
                    ? InputEvent.META_DOWN_MASK
                    : InputEvent.CTRL_DOWN_MASK;
        }
        return Toolkit.getDefaultToolkit().getMenuShortcutKeyMaskEx();
    }

    public static final int CONTROL_OR_CMD_MASK = getControlOrCommandMask();
}
