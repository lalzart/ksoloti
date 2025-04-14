package axoloti.mcp;

import java.util.HashMap;
import java.util.Map;

/**
 * Represents a specification for an object in a patch
 */
public class ObjectSpecification {
    private String id;
    private String type;
    private int x;
    private int y;
    private Map<String, String> parameters;
    
    public ObjectSpecification() {
        parameters = new HashMap<>();
    }
    
    public String getId() {
        return id;
    }
    
    public void setId(String id) {
        this.id = id;
    }
    
    public String getType() {
        return type;
    }
    
    public void setType(String type) {
        this.type = type;
    }
    
    public int getX() {
        return x;
    }
    
    public void setX(int x) {
        this.x = x;
    }
    
    public int getY() {
        return y;
    }
    
    public void setY(int y) {
        this.y = y;
    }
    
    public Map<String, String> getParameters() {
        return parameters;
    }
    
    public void setParameters(Map<String, String> parameters) {
        this.parameters = parameters;
    }
    
    public void addParameter(String key, String value) {
        parameters.put(key, value);
    }
    
    @Override
    public String toString() {
        return "ObjectSpecification{" +
                "id='" + id + '\'' +
                ", type='" + type + '\'' +
                ", x=" + x +
                ", y=" + y +
                ", parameters=" + parameters +
                '}';
    }
} 