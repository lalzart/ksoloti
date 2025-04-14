package axoloti.mcp;

import axoloti.AttributeInstance;
import axoloti.PatchGUI;
import axoloti.object.AxoObjectInstance;
import org.junit.Before;
import org.junit.Test;

import java.util.List;

import static org.junit.Assert.*;

/**
 * Tests for the GillsIntegrationTool class.
 */
public class GillsIntegrationToolTest {

    private PatchGUI patch;

    @Before
    public void setUp() {
        // Create a new patch for each test
        patch = new PatchGUI();
    }

    @Test
    public void testGetGillsObjectType() {
        assertEquals("pot", GillsIntegrationTool.getGillsObjectType("potentiometer"));
        assertEquals("pot", GillsIntegrationTool.getGillsObjectType("knob"));
        assertEquals("pot", GillsIntegrationTool.getGillsObjectType("slider"));
        assertEquals("pot", GillsIntegrationTool.getGillsObjectType("dial"));
        
        assertEquals("button", GillsIntegrationTool.getGillsObjectType("button"));
        assertEquals("button", GillsIntegrationTool.getGillsObjectType("switch"));
        assertEquals("button", GillsIntegrationTool.getGillsObjectType("trigger"));
        
        assertEquals("led", GillsIntegrationTool.getGillsObjectType("led"));
        assertEquals("led", GillsIntegrationTool.getGillsObjectType("light"));
        assertEquals("led", GillsIntegrationTool.getGillsObjectType("indicator"));
        
        assertNull(GillsIntegrationTool.getGillsObjectType("unknown"));
    }

    @Test
    public void testCreateGillsAttributes() {
        AttributeInstance[] attributes = GillsIntegrationTool.createGillsAttributes("pot", "volume");
        assertNotNull(attributes);
        assertEquals(4, attributes.length);
        
        // Check that the purpose is set in the name attribute
        boolean nameFound = false;
        for (AttributeInstance attr : attributes) {
            if (attr.getName().equals("name")) {
                assertEquals("volume", attr.getValue());
                nameFound = true;
                break;
            }
        }
        assertTrue("Name attribute not found or value not set correctly", nameFound);
    }

    @Test
    public void testAddGillsControlsFromDescription_SinglePot() {
        int count = GillsIntegrationTool.addGillsControlsFromDescription(patch, "I need a pot for volume");
        assertEquals(1, count);
        
        List<AxoObjectInstance> objects = patch.getObjectInstances();
        assertEquals(1, objects.size());
        
        AxoObjectInstance obj = objects.get(0);
        assertEquals("gills/in/pot", obj.getType().getId());
        
        // Check name attribute
        AttributeInstance nameAttr = obj.getAttributeInstance("name");
        assertNotNull(nameAttr);
        assertEquals("volume", nameAttr.getValue());
    }

    @Test
    public void testAddGillsControlsFromDescription_MultiplePots() {
        int count = GillsIntegrationTool.addGillsControlsFromDescription(patch, 
                "I need a pot for volume and another pot for frequency");
        assertEquals(2, count);
        
        List<AxoObjectInstance> objects = patch.getObjectInstances();
        assertEquals(2, objects.size());
        
        // Check both objects are pots
        for (AxoObjectInstance obj : objects) {
            assertEquals("gills/in/pot", obj.getType().getId());
        }
        
        // Check names
        boolean volumeFound = false;
        boolean frequencyFound = false;
        
        for (AxoObjectInstance obj : objects) {
            AttributeInstance nameAttr = obj.getAttributeInstance("name");
            assertNotNull(nameAttr);
            
            if ("volume".equals(nameAttr.getValue())) {
                volumeFound = true;
            } else if ("frequency".equals(nameAttr.getValue())) {
                frequencyFound = true;
            }
        }
        
        assertTrue("Volume pot not found", volumeFound);
        assertTrue("Frequency pot not found", frequencyFound);
    }

    @Test
    public void testAddGillsControlsFromDescription_MixedControls() {
        int count = GillsIntegrationTool.addGillsControlsFromDescription(patch, 
                "I need a pot for volume, a button for trigger, and an LED for status");
        assertEquals(3, count);
        
        List<AxoObjectInstance> objects = patch.getObjectInstances();
        assertEquals(3, objects.size());
        
        // Check for one of each type
        boolean potFound = false;
        boolean buttonFound = false;
        boolean ledFound = false;
        
        for (AxoObjectInstance obj : objects) {
            String id = obj.getType().getId();
            
            if ("gills/in/pot".equals(id)) {
                potFound = true;
                AttributeInstance nameAttr = obj.getAttributeInstance("name");
                assertEquals("volume", nameAttr.getValue());
            } else if ("gills/in/button".equals(id)) {
                buttonFound = true;
                AttributeInstance nameAttr = obj.getAttributeInstance("name");
                assertEquals("trigger", nameAttr.getValue());
            } else if ("gills/out/led".equals(id)) {
                ledFound = true;
                AttributeInstance nameAttr = obj.getAttributeInstance("name");
                assertEquals("status", nameAttr.getValue());
            }
        }
        
        assertTrue("Pot not found", potFound);
        assertTrue("Button not found", buttonFound);
        assertTrue("LED not found", ledFound);
    }

    @Test
    public void testAddGillsControlsFromDescription_NoControls() {
        int count = GillsIntegrationTool.addGillsControlsFromDescription(patch, 
                "This description doesn't mention any controls");
        assertEquals(0, count);
        
        List<AxoObjectInstance> objects = patch.getObjectInstances();
        assertEquals(0, objects.size());
    }

    @Test
    public void testAddGillsControlsFromDescription_PositionOffsets() {
        int count = GillsIntegrationTool.addGillsControlsFromDescription(patch, 
                "I need a pot for volume, a pot for cutoff, and a pot for resonance");
        assertEquals(3, count);
        
        List<AxoObjectInstance> objects = patch.getObjectInstances();
        assertEquals(3, objects.size());
        
        // Check that objects have different x,y positions
        for (int i = 0; i < objects.size(); i++) {
            for (int j = i + 1; j < objects.size(); j++) {
                AxoObjectInstance obj1 = objects.get(i);
                AxoObjectInstance obj2 = objects.get(j);
                
                assertFalse("Objects should have different positions",
                        obj1.getX() == obj2.getX() && obj1.getY() == obj2.getY());
            }
        }
    }
} 